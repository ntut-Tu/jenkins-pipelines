package dev.codebase.trace.runtime;

import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.atomic.AtomicLong;

/** Shared in-process recorder. Tokens identify invocations, never time windows. */
public final class TraceRecorder {
    private static final Map<String, Invocation> INVOCATIONS = new ConcurrentHashMap<>();
    private static final ThreadLocal<String> CURRENT = new ThreadLocal<>();
    private static final AtomicLong UNATTRIBUTED = new AtomicLong();
    private static final Set<String> ERRORS = ConcurrentHashMap.newKeySet();
    private static volatile boolean agentAttached;

    private TraceRecorder() {}

    /** Called by premain; detects missing agent or a split runtime class loader. */
    public static void agentAttached() { agentAttached = true; }
    public static boolean hasAgent() { return agentAttached; }

    /** Begin one JUnit invocation and associate the executing thread with it. */
    public static String start(String uniqueId, MethodKey test) {
        String token = UUID.randomUUID().toString();
        INVOCATIONS.put(token, new Invocation(uniqueId, test));
        CURRENT.set(token);
        return token;
    }

    /** End recording before clearing thread state; late work cannot join another test. */
    public static void finish(String token) {
        Invocation invocation = INVOCATIONS.get(token);
        if (invocation != null) {
            synchronized (invocation) { invocation.active = false; }
        }
        if (token.equals(CURRENT.get())) CURRENT.remove();
    }

    /** Return the active test token, or null outside a test-associated operation. */
    public static String currentToken() {
        String token = CURRENT.get();
        return isActive(token) ? token : null;
    }

    private static boolean isActive(String token) {
        Invocation invocation = token == null ? null : INVOCATIONS.get(token);
        if (invocation == null) return false;
        synchronized (invocation) { return invocation.active; }
    }

    /** Attach an already-issued token on a server thread and restore its prior state. */
    public static Scope attach(String token) {
        String previous = CURRENT.get();
        if (isActive(token)) CURRENT.set(token); else CURRENT.remove();
        return new Scope(previous);
    }

    /** Record a method entry. Calls without a known active token are never attributed. */
    public static void hit(String owner, String name, String descriptor) {
        String token = CURRENT.get();
        Invocation invocation = token == null ? null : INVOCATIONS.get(token);
        if (invocation != null) {
            synchronized (invocation) {
                if (invocation.active) {
                    invocation.calls.add(new MethodKey(owner, name, descriptor));
                    return;
                }
            }
        }
        UNATTRIBUTED.incrementAndGet();
    }

    public static void error(String detail) { ERRORS.add(detail); }
    public static List<String> errors() { return ERRORS.stream().sorted().toList(); }
    public static long unattributedCalls() { return UNATTRIBUTED.get(); }

    /** Copy completed observations without exposing mutable recorder state. */
    public static List<Observation> snapshot() {
        List<Observation> result = new ArrayList<>();
        INVOCATIONS.values().forEach(invocation -> {
            synchronized (invocation) {
                if (invocation.active) ERRORS.add("Invocation still active at export");
                result.add(new Observation(invocation.uniqueId, invocation.test, Set.copyOf(invocation.calls)));
            }
        });
        result.sort(java.util.Comparator.comparing(Observation::uniqueId));
        return List.copyOf(result);
    }

    /** Immutable raw invocation; uniqueId keeps parameterized cases separate internally. */
    public record Observation(String uniqueId, MethodKey test, Set<MethodKey> calls) {}

    /** Lexical context boundary, intended for try-with-resources in the HTTP filter. */
    public static final class Scope implements AutoCloseable {
        private final String previous;
        private Scope(String previous) { this.previous = previous; }
        @Override public void close() {
            if (previous == null) CURRENT.remove(); else CURRENT.set(previous);
        }
    }

    private static final class Invocation {
        private final String uniqueId;
        private final MethodKey test;
        private final Set<MethodKey> calls = new HashSet<>();
        private boolean active = true;
        private Invocation(String uniqueId, MethodKey test) { this.uniqueId = uniqueId; this.test = test; }
    }
}

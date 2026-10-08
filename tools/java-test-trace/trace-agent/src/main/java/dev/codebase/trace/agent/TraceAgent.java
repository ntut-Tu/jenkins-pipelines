package dev.codebase.trace.agent;

import static net.bytebuddy.matcher.ElementMatchers.isAbstract;
import static net.bytebuddy.matcher.ElementMatchers.isMethod;
import static net.bytebuddy.matcher.ElementMatchers.isNative;
import static net.bytebuddy.matcher.ElementMatchers.isSynthetic;
import static net.bytebuddy.matcher.ElementMatchers.nameStartsWith;
import static net.bytebuddy.matcher.ElementMatchers.namedOneOf;
import static net.bytebuddy.matcher.ElementMatchers.not;

import java.lang.instrument.Instrumentation;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;

import net.bytebuddy.description.type.TypeDescription;
import net.bytebuddy.matcher.ElementMatcher;

import net.bytebuddy.agent.builder.AgentBuilder;
import net.bytebuddy.asm.Advice;
import net.bytebuddy.utility.JavaModule;

import dev.codebase.trace.runtime.TraceRecorder;

/** Instruments methods only in the configured application package. */
public final class TraceAgent {
    private TraceAgent() {}

    public static void premain(String arguments, Instrumentation instrumentation) throws IOException {
        String include = System.getProperty("trace.include", "");
        if (include.isBlank() || !include.endsWith(".")) {
            throw new IllegalArgumentException("trace.include must be a nonempty package prefix ending in '.'");
        }
        ElementMatcher.Junction<TypeDescription> types = nameStartsWith(include).and(not(isSynthetic()));
        String classFile = System.getProperty("trace.classes", "");
        if (!classFile.isBlank()) {
            String[] classes = Files.readAllLines(Path.of(classFile)).stream()
                .map(String::trim).filter(name -> !name.isEmpty()).toArray(String[]::new);
            if (classes.length == 0) throw new IllegalArgumentException("Empty trace.classes allowlist");
            for (String name : classes) {
                if (!name.startsWith(include)) throw new IllegalArgumentException("Class outside trace.include: " + name);
            }
            // Exact source-backed types exclude generated jOOQ, proxy, and test classes.
            // Nested classes are outside this integration's explicitly partial scope.
            types = types.and(namedOneOf(classes));
        }
        TraceRecorder.agentAttached();
        new AgentBuilder.Default()
            .disableClassFormatChanges()
            .type(types)
            .transform((builder, type, loader, module, domain) -> builder.visit(
                Advice.to(MethodEntry.class).on(isMethod().and(not(isAbstract())).and(not(isNative())).and(not(isSynthetic())))))
            .with(new AgentBuilder.Listener.Adapter() {
                @Override public void onError(String typeName, ClassLoader loader, JavaModule module, boolean loaded, Throwable error) {
                    TraceRecorder.error("Instrumentation failed: " + typeName);
                }
            })
            .installOn(instrumentation);
    }

    /** Advice is inlined; the application's bytecode calls only the small runtime API. */
    public static final class MethodEntry {
        @Advice.OnMethodEnter
        public static void enter(@Advice.Origin("#t") String owner,
                                 @Advice.Origin("#m") String method,
                                 @Advice.Origin("#d") String descriptor) {
            TraceRecorder.hit(owner, method, descriptor);
        }
    }
}

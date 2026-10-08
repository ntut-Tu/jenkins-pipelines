package dev.codebase.trace.agent;

import static net.bytebuddy.matcher.ElementMatchers.isAbstract;
import static net.bytebuddy.matcher.ElementMatchers.isMethod;
import static net.bytebuddy.matcher.ElementMatchers.isNative;
import static net.bytebuddy.matcher.ElementMatchers.isSynthetic;
import static net.bytebuddy.matcher.ElementMatchers.nameStartsWith;
import static net.bytebuddy.matcher.ElementMatchers.not;

import java.lang.instrument.Instrumentation;

import net.bytebuddy.agent.builder.AgentBuilder;
import net.bytebuddy.asm.Advice;
import net.bytebuddy.utility.JavaModule;

import dev.codebase.trace.runtime.TraceRecorder;

/** Instruments methods only in the configured application package. */
public final class TraceAgent {
    private TraceAgent() {}

    public static void premain(String arguments, Instrumentation instrumentation) {
        String include = System.getProperty("trace.include", "");
        if (include.isBlank() || !include.endsWith(".")) {
            throw new IllegalArgumentException("trace.include must be a nonempty package prefix ending in '.'");
        }
        TraceRecorder.agentAttached();
        new AgentBuilder.Default()
            .disableClassFormatChanges()
            .type(nameStartsWith(include).and(not(isSynthetic())))
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

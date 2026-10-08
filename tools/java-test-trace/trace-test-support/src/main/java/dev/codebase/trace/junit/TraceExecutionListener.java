package dev.codebase.trace.junit;

import java.lang.invoke.MethodType;
import java.lang.reflect.Method;
import java.nio.file.Path;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

import org.junit.platform.engine.TestExecutionResult;
import org.junit.platform.engine.support.descriptor.MethodSource;
import org.junit.platform.launcher.TestExecutionListener;
import org.junit.platform.launcher.TestIdentifier;
import org.junit.platform.launcher.TestPlan;

import dev.codebase.trace.output.ObservationWriter;
import dev.codebase.trace.runtime.MethodKey;
import dev.codebase.trace.runtime.TraceRecorder;
import dev.codebase.trace.source.SourceResolver;

/** JUnit Platform listener activated only by the explicit spike system property. */
public final class TraceExecutionListener implements TestExecutionListener {
    private final Map<String, String> tokens = new ConcurrentHashMap<>();
    private final boolean enabled = Boolean.getBoolean("trace.enabled");

    @Override public void executionStarted(TestIdentifier test) {
        if (!enabled || !test.isTest()) return;
        if (!(test.getSource().orElse(null) instanceof MethodSource source)) {
            TraceRecorder.error("Unsupported test source: " + test.getUniqueId());
            return;
        }
        Method method = source.getJavaMethod();
        String descriptor = MethodType.methodType(method.getReturnType(), method.getParameterTypes()).toMethodDescriptorString();
        String token = TraceRecorder.start(test.getUniqueId(), new MethodKey(method.getDeclaringClass().getName(), method.getName(), descriptor));
        tokens.put(test.getUniqueId(), token);
    }

    @Override public void executionFinished(TestIdentifier test, TestExecutionResult result) {
        String token = tokens.remove(test.getUniqueId());
        if (token != null) TraceRecorder.finish(token);
    }

    @Override public void testPlanExecutionFinished(TestPlan plan) {
        if (!enabled) return;
        try {
            if (!TraceRecorder.hasAgent()) throw new IllegalStateException("Trace Java agent was not attached");
            new ObservationWriter(new SourceResolver(Path.of(System.getProperty("trace.sourceRoot"))))
                .write(Path.of(System.getProperty("trace.output")));
        } catch (Exception error) {
            // JUnit logs listener failures; the finalizer also requires this artifact.
            throw new IllegalStateException("Trace export failed", error);
        }
    }
}

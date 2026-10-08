package dev.codebase.trace.output;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import com.fasterxml.jackson.databind.ObjectMapper;

import dev.codebase.trace.runtime.MethodKey;
import dev.codebase.trace.runtime.TraceRecorder;
import dev.codebase.trace.source.SourceResolver;

/** Writes raw observations after JUnit finishes; XML hashing occurs after JaCoCo report. */
public final class ObservationWriter {
    private final SourceResolver sources;
    private final ObjectMapper json = new ObjectMapper();
    public ObservationWriter(SourceResolver sources) { this.sources = sources; }

    public void write(Path output) throws IOException {
        List<Map<String, Object>> tests = new ArrayList<>();
        for (TraceRecorder.Observation observation : TraceRecorder.snapshot()) {
            List<SourceResolver.Reference> calls = new ArrayList<>();
            for (MethodKey call : observation.calls().stream().sorted(Comparator.comparing(MethodKey::toString)).toList()) {
                calls.add(sources.resolve(call));
            }
            tests.add(Map.of("test", sources.resolve(observation.test()), "calls", calls));
        }
        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put("tests", tests);
        payload.put("diagnostics", Map.of("agent_attached", TraceRecorder.hasAgent(), "unattributed_calls", TraceRecorder.unattributedCalls(), "errors", TraceRecorder.errors()));
        Files.createDirectories(output.toAbsolutePath().getParent());
        json.writerWithDefaultPrettyPrinter().writeValue(output.toFile(), payload);
    }
}

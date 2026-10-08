package dev.codebase.trace.output;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.HexFormat;
import java.util.LinkedHashMap;
import java.util.Map;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;

/** Finalizes CI trace after coverage XML exists, without the Python/LLM application. */
public final class TraceArtifactAssembler {
    private final ObjectMapper json = new ObjectMapper();

    /**
     * Bind producer observations to a tested revision and the exact XML bytes.
     *
     * @param observations completed Java recorder output
     * @param coverage matching coverage XML from the same test run
     * @param revision actual tested source revision; zero SHA is reserved for the fixture
     * @param buildId producer build identifier
     * @param scope supported execution scope, not a completeness claim
     * @param output final version-1 trace artifact
     * @throws IOException when observations or required files are missing/invalid
     * @throws NoSuchAlgorithmException if the runtime cannot provide SHA-256
     */
    public void assemble(Path observations, Path coverage, String revision,
                         String buildId, String scope, Path output)
            throws IOException, NoSuchAlgorithmException {
        if (!revision.matches("(?:[a-f0-9]{40}|[a-f0-9]{64})") || buildId.isBlank() || scope.isBlank()) {
            throw new IllegalArgumentException("Require full source SHA, build ID, and scope");
        }
        JsonNode raw = json.readTree(observations.toFile());
        JsonNode diagnostics = raw.path("diagnostics");
        if (!diagnostics.path("agent_attached").asBoolean(false)
                || !diagnostics.path("errors").isArray() || !diagnostics.path("errors").isEmpty()
                || !raw.path("tests").isArray() || raw.path("tests").isEmpty()) {
            throw new IOException("Missing agent, failed tracing, or empty observations");
        }
        byte[] xml = Files.readAllBytes(coverage);
        if (xml.length == 0) throw new IOException("Coverage XML is empty");
        String digest = HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(xml));
        Map<String, Object> artifact = new LinkedHashMap<>();
        artifact.put("schema_version", 1);
        artifact.put("revision", revision);
        artifact.put("coverage_sha256", digest);
        artifact.put("build_id", buildId);
        artifact.put("scope", scope);
        artifact.put("complete", false);
        artifact.put("tests", raw.get("tests"));
        Files.createDirectories(output.toAbsolutePath().getParent());
        json.writerWithDefaultPrettyPrinter().writeValue(output.toFile(), artifact);
    }

    /** Maven/CI entry point; all paths and provenance are explicit arguments. */
    public static void main(String[] args) throws Exception {
        if (args.length != 6) {
            throw new IllegalArgumentException("Expected: observations coverage revision buildId scope output");
        }
        new TraceArtifactAssembler().assemble(Path.of(args[0]), Path.of(args[1]),
                args[2], args[3], args[4], Path.of(args[5]));
        System.out.println("[PASS] Producer finalized coverage-bound trace: " + args[5]);
    }
}

package dev.codebase.trace.source;

import java.io.IOException;
import java.io.InputStream;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.HashMap;
import java.util.Map;

import org.objectweb.asm.ClassReader;
import org.objectweb.asm.ClassVisitor;
import org.objectweb.asm.Label;
import org.objectweb.asm.MethodVisitor;
import org.objectweb.asm.Opcodes;

import dev.codebase.trace.runtime.MethodKey;

/** Resolves JVM descriptors using class debug tables and explicit Maven source roots. */
public final class SourceResolver {
    private final Path repository;
    private final Map<String, Map<MethodKey, Reference>> cache = new HashMap<>();

    public SourceResolver(Path repository) { this.repository = repository.toAbsolutePath().normalize(); }

    /** Find a line inside the method; ambiguous or missing source is a hard export error. */
    public Reference resolve(MethodKey key) throws IOException {
        if (!cache.containsKey(key.className())) cache.put(key.className(), inspect(key.className()));
        Reference result = cache.get(key.className()).get(key);
        if (result == null) throw new IOException("Missing method debug information: " + key);
        return result;
    }

    private Map<MethodKey, Reference> inspect(String owner) throws IOException {
        String resource = owner.replace('.', '/') + ".class";
        Map<MethodKey, Reference> result = new HashMap<>();
        try (InputStream input = Thread.currentThread().getContextClassLoader().getResourceAsStream(resource)) {
            if (input == null) throw new IOException("Missing class resource: " + owner);
            new ClassReader(input).accept(new ClassVisitor(Opcodes.ASM9) {
                private String sourceFile;
                @Override public void visitSource(String source, String debug) { sourceFile = source; }
                @Override public MethodVisitor visitMethod(int access, String name, String descriptor, String signature, String[] exceptions) {
                    return new MethodVisitor(Opcodes.ASM9) {
                        private int firstLine = Integer.MAX_VALUE;
                        @Override public void visitLineNumber(int line, Label label) { if (line > 0) firstLine = Math.min(firstLine, line); }
                        @Override public void visitEnd() {
                            if (sourceFile == null || firstLine == Integer.MAX_VALUE) return;
                            String packagePath = owner.contains(".") ? owner.substring(0, owner.lastIndexOf('.')).replace('.', '/') + "/" : "";
                            String relative = packagePath + sourceFile;
                            String path = null;
                            for (String root : new String[]{"src/main/java/", "src/test/java/"}) {
                                Path candidate = repository.resolve(root + relative).normalize();
                                if (!candidate.startsWith(repository)) throw new IllegalStateException("Invalid source path");
                                if (Files.isRegularFile(candidate)) {
                                    if (path != null) throw new IllegalStateException("Ambiguous source: " + owner);
                                    path = root + relative;
                                }
                            }
                            if (path != null) result.put(new MethodKey(owner, name, descriptor), new Reference(path, owner.replace('$', '.'), name, firstLine));
                        }
                    };
                }
            }, ClassReader.SKIP_FRAMES);
        }
        return result;
    }

    /** JSON field names match the Python version-1 method reference contract. */
    public record Reference(String path, String class_name, String name, int line) {}
}

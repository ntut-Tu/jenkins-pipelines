package dev.codebase.trace.runtime;

/** JVM identity retains a descriptor to distinguish overloaded methods. */
public record MethodKey(String className, String name, String descriptor) {}

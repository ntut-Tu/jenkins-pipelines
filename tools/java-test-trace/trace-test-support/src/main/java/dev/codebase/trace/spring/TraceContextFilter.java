package dev.codebase.trace.spring;

import java.io.IOException;

import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;

import org.springframework.web.filter.OncePerRequestFilter;

import dev.codebase.trace.runtime.TraceRecorder;

/** Associates synchronous servlet dispatch with an already-active in-JVM test token. */
public final class TraceContextFilter extends OncePerRequestFilter {
    public static final String HEADER = "X-Codebase-Test-Trace";

    @Override protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response, FilterChain chain)
            throws ServletException, IOException {
        try (TraceRecorder.Scope scope = TraceRecorder.attach(request.getHeader(HEADER))) {
            chain.doFilter(request, response);
        }
    }
}

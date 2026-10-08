package dev.codebase.trace.spring;

import java.util.ArrayList;
import java.util.Set;

import org.springframework.beans.factory.config.BeanPostProcessor;
import org.springframework.boot.test.web.client.TestRestTemplate;
import org.springframework.core.env.Environment;
import org.springframework.http.client.ClientHttpRequestInterceptor;
import org.springframework.web.client.RestTemplate;

import dev.codebase.trace.runtime.TraceRecorder;

/** Adds correlation only to the same embedded test server, never arbitrary destinations. */
public final class TraceRestTemplatePostProcessor implements BeanPostProcessor {
    private final Environment environment;
    public TraceRestTemplatePostProcessor(Environment environment) { this.environment = environment; }

    @Override public Object postProcessAfterInitialization(Object bean, String name) {
        RestTemplate template = bean instanceof TestRestTemplate test ? test.getRestTemplate()
            : bean instanceof RestTemplate rest ? rest : null;
        if (template != null) {
            var interceptors = new ArrayList<ClientHttpRequestInterceptor>(template.getInterceptors());
            interceptors.add((request, body, execution) -> {
                String token = TraceRecorder.currentToken();
                String port = environment.getProperty("local.server.port");
                if (token != null && port != null && Set.of("localhost", "127.0.0.1", "[::1]", "::1").contains(request.getURI().getHost())
                        && request.getURI().getPort() == Integer.parseInt(port)) {
                    request.getHeaders().set(TraceContextFilter.HEADER, token);
                }
                return execution.execute(request, body);
            });
            template.setInterceptors(interceptors);
        }
        return bean;
    }
}

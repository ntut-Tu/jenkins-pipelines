package dev.codebase.trace.spring;

import org.springframework.boot.autoconfigure.AutoConfiguration;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.boot.web.servlet.FilterRegistrationBean;
import org.springframework.context.annotation.Bean;
import org.springframework.core.Ordered;
import org.springframework.core.env.Environment;

/** Test-classpath-only, opt-in Spring support for the synchronous HTTP spike. */
@AutoConfiguration
@ConditionalOnProperty(name = "trace.enabled", havingValue = "true")
public class TraceAutoConfiguration {
    @Bean public static TraceRestTemplatePostProcessor traceRestTemplatePostProcessor(Environment environment) {
        return new TraceRestTemplatePostProcessor(environment);
    }
    @Bean public FilterRegistrationBean<TraceContextFilter> traceContextFilter() {
        FilterRegistrationBean<TraceContextFilter> registration = new FilterRegistrationBean<>(new TraceContextFilter());
        registration.setOrder(Ordered.HIGHEST_PRECEDENCE);
        return registration;
    }
}

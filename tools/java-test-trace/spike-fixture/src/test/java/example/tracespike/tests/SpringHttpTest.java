package example.tracespike.tests;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.parallel.Execution;
import org.junit.jupiter.api.parallel.ExecutionMode;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.client.TestRestTemplate;
import org.springframework.boot.test.web.server.LocalServerPort;
import org.springframework.web.client.RestTemplate;

import example.tracespike.app.FixtureApplication;

/** Parallel real HTTP calls must retain separate invocation identities. */
@SpringBootTest(classes = FixtureApplication.class, webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
@Execution(ExecutionMode.CONCURRENT)
class SpringHttpTest {
    @Autowired TestRestTemplate http;
    @LocalServerPort int port;

    @Test void firstRequest() {
        // An unmanaged client deliberately sends no token: do not infer ownership by time.
        assertEquals("background", new RestTemplate().getForObject("http://localhost:" + port + "/background", String.class));
        String response = http.getForObject("/first", String.class);
        assertNotNull(response);
        assertTrue(response.startsWith("first:"));
        assertFalse(response.endsWith(Thread.currentThread().getName()));
    }

    @Test void secondRequest() {
        String response = http.getForObject("/second", String.class);
        assertNotNull(response);
        assertTrue(response.startsWith("second:"));
        assertFalse(response.endsWith(Thread.currentThread().getName()));
    }
}

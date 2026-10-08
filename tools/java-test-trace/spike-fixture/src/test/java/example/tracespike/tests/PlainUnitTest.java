package example.tracespike.tests;

import static org.junit.jupiter.api.Assertions.assertEquals;

import org.junit.jupiter.api.Test;

import example.tracespike.app.WorkService;

/** Direct invocation also proves overload descriptors map to the right source method. */
class PlainUnitTest {
    @Test void directMethod() { assertEquals(4, new WorkService().calculate(3)); }
}

package example.tracespike.app;

import java.util.concurrent.CyclicBarrier;
import java.util.concurrent.TimeUnit;

import org.springframework.stereotype.Service;

/** Distinct paths plus a barrier prove two HTTP requests overlap during tracing. */
@Service
public class WorkService {
    private final CyclicBarrier barrier = new CyclicBarrier(2);
    public String first() { rendezvous(); return "first:" + Thread.currentThread().getName(); }
    public String second() { rendezvous(); return "second:" + Thread.currentThread().getName(); }
    public String background() { return "background"; }
    public int calculate(int value) { return value + 1; }
    public int calculate(String value) { return value.length(); }
    private void rendezvous() {
        try { barrier.await(15, TimeUnit.SECONDS); }
        catch (Exception error) { throw new IllegalStateException("HTTP requests did not overlap", error); }
    }
}

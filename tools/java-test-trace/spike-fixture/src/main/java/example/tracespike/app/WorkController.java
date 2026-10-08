package example.tracespike.app;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

/** HTTP entry points delegate to a composed service. */
@RestController
public class WorkController {
    private final WorkService service;
    public WorkController(WorkService service) { this.service = service; }
    @GetMapping("/first") public String first() { return service.first(); }
    @GetMapping("/second") public String second() { return service.second(); }
    @GetMapping("/background") public String background() { return service.background(); }
}

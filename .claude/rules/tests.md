---
paths:
  - "tests/**"
  - "pytest.ini"
---
# Tests
- `python -m pytest` runs everything (~80 s, real Railway DB). `-m "not db_write"` skips the tests that write rows.
- Throwaway data only: bookings via the `booking` / `throwaway` fixtures (ids 9990xxxxxx, deleted after), templates named
  `ZZ TEST …` deleted in `finally`. Never touch real guests' rows.
- Add a test for every bug the owner reports (a real screenshot's text makes the best parser test).

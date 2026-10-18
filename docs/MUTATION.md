# Mutation check

**12/12 injected bugs were caught by the test suite.**

Each row is a deliberate bug put into the engine; the suite must fail for it to count as killed.

| Injected bug | File | Result |
|---|---|---|
| priority order reversed | core.py | killed |
| round-robin quantum off by one | core.py | killed |
| context switches over-counted | core.py | killed |
| response time ignores arrival | core.py | killed |
| preempts one tick early | core.py | killed |
| tie-break prefers later arrival | core.py | killed |
| LRU evicts most recent page | memory.py | killed |
| FIFO evicts newest page | memory.py | killed |
| detection too strict | deadlock.py | killed |
| Banker's safety too strict | deadlock.py | killed |
| cpu rule inverted | security.py | killed |
| kernel validation always passes | evidence.py | killed |

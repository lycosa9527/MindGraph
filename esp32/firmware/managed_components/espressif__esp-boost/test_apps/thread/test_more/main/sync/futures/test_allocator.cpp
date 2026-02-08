#include "test_allocator.hpp"

/* esp32: avoid redefinition */
int test_alloc_base::count = 0;
int test_alloc_base::throw_after = INT_MAX;

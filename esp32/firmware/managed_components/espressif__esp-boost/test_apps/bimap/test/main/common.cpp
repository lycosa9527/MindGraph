#include "common.hpp"
#include <boost/detail/lightweight_test.hpp>

void common_init() {
  boost::detail::test_results().errors() = 0;
}

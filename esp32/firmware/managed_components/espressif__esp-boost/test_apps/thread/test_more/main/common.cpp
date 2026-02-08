#include <new>
#include <cstdlib>
#include <cassert>
#include "common.hpp"
#include <boost/thread/thread_only.hpp>
#include <boost/detail/lightweight_test.hpp>

unsigned throw_one = 0xFFFF;

#if defined _GLIBCXX_THROW
void* operator new(std::size_t s) _GLIBCXX_THROW (std::bad_alloc)
#elif defined BOOST_MSVC
void* operator new(std::size_t s)
#elif __cplusplus > 201402L
void* operator new(std::size_t s)
#else
void* operator new(std::size_t s) throw (std::bad_alloc)
#endif
{
  //std::cout << __FILE__ << ":" << __LINE__ << std::endl;
  if (throw_one == 0) throw std::bad_alloc();
  --throw_one;
  return std::malloc(s);
}

#if defined BOOST_MSVC
void operator delete(void* p)
#else
void operator delete(void* p) BOOST_NOEXCEPT_OR_NOTHROW
#endif
{
  //std::cout << __FILE__ << ":" << __LINE__ << std::endl;
  std::free(p);
}

void common_init() {
  boost::detail::test_results().errors() = 0;
  throw_one = 0xFFFF;
}

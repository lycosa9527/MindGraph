#include <stdexcept>

#include <boost/exception/exception.hpp>
#include <boost/throw_exception.hpp>

#include "common.hpp"
namespace {

struct hex_decode_error : virtual boost::exception, virtual std::exception {};
struct not_enough_input : virtual hex_decode_error {};
struct non_hex_input    : virtual hex_decode_error {};

void toss() { BOOST_THROW_EXCEPTION(not_enough_input()); }

int main () {
	try { toss(); }
	catch ( const hex_decode_error & /*ex*/ ) {}
	return 0;
	}

} // namespace

BOOST_AUTO_TEST_CASE(mclow)
{
    TEST_ASSERT(main() == 0);
}
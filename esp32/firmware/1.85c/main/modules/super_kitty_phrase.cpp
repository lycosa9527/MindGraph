#include "super_kitty_phrase.hpp"

#include <cctype>
#include <string>
#include <vector>

namespace {

std::string fold(const std::string &text)
{
    std::string out;
    out.reserve(text.size());
    for (unsigned char ch : text) {
        if (ch == ' ' || ch == '\t' || ch == ',' || ch == '.' || ch == '!' || ch == '?'
            || ch == ':' || ch == ';' || ch == '\'' || ch == '"') {
            continue;
        }
        if (ch < 128U) {
            out.push_back(static_cast<char>(std::tolower(ch)));
        } else {
            out.push_back(static_cast<char>(ch));
        }
    }
    return out;
}

const std::vector<std::string> &folded_prefixes()
{
    static const std::vector<std::string> k_prefixes = {
        "你好kitty",
        "你好凯蒂",
        "你好小猫",
        "nihaokitty",
        "nihaokaidi",
        "nihaoxiaomao",
    };
    return k_prefixes;
}

const std::vector<std::string> &raw_prefixes()
{
    static const std::vector<std::string> k_raw = {
        "你好 kitty",
        "你好Kitty",
        "你好kitty",
        "你好凯蒂",
        "你好小猫",
        "ni hao kitty",
        "Ni hao kitty",
        "nihao kitty",
        "ni hao Kitty",
    };
    return k_raw;
}

bool ascii_ieq(char left, char right)
{
    return std::tolower(static_cast<unsigned char>(left))
        == std::tolower(static_cast<unsigned char>(right));
}

size_t find_raw_prefix(const std::string &text)
{
    for (const std::string &prefix : raw_prefixes()) {
        if (text.size() < prefix.size()) {
            continue;
        }
        bool match = true;
        for (size_t i = 0; i < prefix.size(); ++i) {
            const unsigned char a = static_cast<unsigned char>(text[i]);
            const unsigned char b = static_cast<unsigned char>(prefix[i]);
            if (a < 128U && b < 128U) {
                if (!ascii_ieq(static_cast<char>(a), static_cast<char>(b))) {
                    match = false;
                    break;
                }
            } else if (a != b) {
                match = false;
                break;
            }
        }
        if (match) {
            return prefix.size();
        }
    }
    return 0;
}

} // namespace

bool super_kitty_phrase_is_address(const std::string &text)
{
    if (find_raw_prefix(text) > 0) {
        return true;
    }
    const std::string folded = fold(text);
    for (const std::string &prefix : folded_prefixes()) {
        if (folded.find(prefix) != std::string::npos) {
            return true;
        }
    }
    return false;
}

std::string super_kitty_phrase_strip(const std::string &text)
{
    size_t skip = find_raw_prefix(text);
    if (skip == 0) {
        return text;
    }
    while (skip < text.size()) {
        const unsigned char ch = static_cast<unsigned char>(text[skip]);
        if (ch == ' ' || ch == '\t' || ch == ',' || ch == '.' || ch == '!' || ch == '?') {
            ++skip;
            continue;
        }
        if (ch == 0xE3 && skip + 2 < text.size()
            && static_cast<unsigned char>(text[skip + 1]) == 0x80
            && static_cast<unsigned char>(text[skip + 2]) == 0x81) {
            skip += 3;
            continue;
        }
        if (ch == 0xEF && skip + 2 < text.size()
            && static_cast<unsigned char>(text[skip + 1]) == 0xBC
            && static_cast<unsigned char>(text[skip + 2]) == 0x8C) {
            skip += 3;
            continue;
        }
        break;
    }
    if (skip >= text.size()) {
        return {};
    }
    return text.substr(skip);
}

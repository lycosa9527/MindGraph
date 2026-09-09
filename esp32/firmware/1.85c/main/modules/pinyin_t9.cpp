/*
 * SPDX-FileCopyrightText: 2026 北京思源智教科技有限公司
 *
 * SPDX-License-Identifier: CC0-1.0
 */
#include "pinyin_t9.hpp"

#include <cstring>

namespace {

constexpr PinyinEntry k_dict[] = {
    {"a", "啊阿"},
    {"ai", "爱矮"},
    {"an", "安按暗"},
    {"ang", "昂"},
    {"ao", "奥傲"},
    {"ba", "把八吧爸"},
    {"bai", "白百"},
    {"ban", "半办班"},
    {"bang", "帮棒"},
    {"bao", "包报保"},
    {"bei", "被北杯备"},
    {"ben", "本"},
    {"bi", "比必笔"},
    {"bian", "边变便"},
    {"biao", "表"},
    {"bie", "别"},
    {"bin", "宾"},
    {"bing", "并病冰"},
    {"bo", "波伯"},
    {"bu", "不步部"},
    {"cai", "才菜彩"},
    {"can", "参残"},
    {"cang", "藏仓"},
    {"cao", "草操"},
    {"ce", "测册"},
    {"ceng", "曾层"},
    {"cha", "查茶差"},
    {"chai", "拆"},
    {"chan", "产"},
    {"chang", "长常场唱"},
    {"chao", "超朝"},
    {"che", "车"},
    {"chen", "陈沉"},
    {"cheng", "成城程"},
    {"chi", "吃持尺赤"},
    {"chong", "冲重"},
    {"chou", "抽丑"},
    {"chu", "出初除"},
    {"chuan", "传船川"},
    {"chuang", "创窗床"},
    {"chun", "春"},
    {"ci", "此次词"},
    {"cong", "从"},
    {"cu", "粗促"},
    {"cun", "村存"},
    {"cuo", "错"},
    {"da", "大打答达"},
    {"dai", "带代待"},
    {"dan", "但单担"},
    {"dang", "当党"},
    {"dao", "到道导岛"},
    {"de", "的得地"},
    {"deng", "等灯"},
    {"di", "地第低弟"},
    {"dian", "点电店"},
    {"diao", "调掉"},
    {"ding", "定顶"},
    {"dong", "东动冬懂"},
    {"dou", "都斗豆"},
    {"du", "读度独"},
    {"duan", "短段断"},
    {"dui", "对队"},
    {"duo", "多"},
    {"e", "饿额"},
    {"en", "恩"},
    {"er", "而二儿"},
    {"fa", "发法"},
    {"fan", "反饭烦"},
    {"fang", "方放房"},
    {"fei", "飞非费"},
    {"fen", "分份"},
    {"feng", "风封"},
    {"fou", "否"},
    {"fu", "服父复附"},
    {"gai", "该改"},
    {"gan", "干感敢"},
    {"gang", "刚钢"},
    {"gao", "高告"},
    {"ge", "个各歌"},
    {"gei", "给"},
    {"gen", "跟根"},
    {"geng", "更"},
    {"gong", "工公共"},
    {"gou", "够狗构"},
    {"gu", "古故顾"},
    {"gua", "挂瓜"},
    {"guai", "怪"},
    {"guan", "关管观"},
    {"guang", "光广"},
    {"gui", "贵归"},
    {"gun", "滚"},
    {"guo", "国过果"},
    {"ha", "哈"},
    {"hai", "还海孩"},
    {"han", "汉含寒"},
    {"hang", "行航"},
    {"hao", "好号"},
    {"he", "和何合河"},
    {"hei", "黑"},
    {"hen", "很恨"},
    {"heng", "横"},
    {"hong", "红"},
    {"hou", "后候"},
    {"hu", "和护户"},
    {"hua", "话花化画"},
    {"huai", "坏"},
    {"huan", "还换欢"},
    {"huang", "黄"},
    {"hui", "会回灰"},
    {"hun", "混婚"},
    {"huo", "或活火"},
    {"ji", "机及己记几"},
    {"jia", "家加价"},
    {"jian", "见间件建"},
    {"jiang", "将讲江"},
    {"jiao", "教叫交"},
    {"jie", "解接结姐"},
    {"jin", "进今金近"},
    {"jing", "经京精"},
    {"jiu", "就九久旧"},
    {"ju", "据句举"},
    {"juan", "卷"},
    {"jue", "觉决"},
    {"jun", "军"},
    {"ka", "卡"},
    {"kai", "开"},
    {"kan", "看"},
    {"kao", "考靠"},
    {"ke", "可课客"},
    {"ken", "肯"},
    {"kong", "空控"},
    {"kou", "口"},
    {"ku", "苦哭"},
    {"kuai", "快块"},
    {"kuan", "宽"},
    {"kuang", "况矿"},
    {"kun", "困"},
    {"la", "拉啦"},
    {"lai", "来"},
    {"lan", "蓝兰懒"},
    {"lang", "浪朗"},
    {"lao", "老"},
    {"le", "了乐"},
    {"lei", "类累"},
    {"leng", "冷"},
    {"li", "里力理立利"},
    {"lian", "连脸练"},
    {"liang", "两亮量"},
    {"liao", "了料"},
    {"lie", "列"},
    {"lin", "林临"},
    {"ling", "另令零"},
    {"liu", "六流留"},
    {"long", "龙"},
    {"lou", "楼"},
    {"lu", "路录"},
    {"luan", "乱"},
    {"lun", "论轮"},
    {"luo", "落罗"},
    {"lv", "绿律旅"},
    {"ma", "吗妈马嘛"},
    {"mai", "买卖"},
    {"man", "满慢"},
    {"mang", "忙"},
    {"mao", "毛猫"},
    {"me", "么"},
    {"mei", "没美每"},
    {"men", "们门"},
    {"meng", "梦猛"},
    {"mi", "米密"},
    {"mian", "面免"},
    {"miao", "秒妙"},
    {"min", "民敏"},
    {"ming", "明名"},
    {"mo", "莫摸"},
    {"mou", "某"},
    {"mu", "目母木"},
    {"na", "那拿哪"},
    {"nai", "奶耐"},
    {"nan", "男难南"},
    {"nao", "脑闹"},
    {"ne", "呢"},
    {"nei", "内"},
    {"nen", "嫩"},
    {"neng", "能"},
    {"ni", "你呢尼"},
    {"nian", "年念"},
    {"niang", "娘"},
    {"niao", "鸟"},
    {"nin", "您"},
    {"ning", "宁凝"},
    {"niu", "牛"},
    {"nong", "农弄"},
    {"nu", "怒努"},
    {"nuan", "暖"},
    {"nv", "女"},
    {"ou", "欧偶"},
    {"pa", "怕爬"},
    {"pai", "排拍"},
    {"pan", "盘判"},
    {"pang", "旁胖"},
    {"pao", "跑"},
    {"pei", "配陪"},
    {"pen", "盆"},
    {"peng", "朋碰"},
    {"pi", "皮批"},
    {"pian", "片便"},
    {"piao", "票飘"},
    {"pin", "品贫"},
    {"ping", "平评"},
    {"po", "破迫"},
    {"pu", "普铺"},
    {"qi", "起其七气期"},
    {"qia", "恰"},
    {"qian", "前钱千"},
    {"qiang", "强墙"},
    {"qiao", "桥巧"},
    {"qie", "且切"},
    {"qin", "亲琴"},
    {"qing", "请情清轻"},
    {"qiong", "穷"},
    {"qiu", "求秋球"},
    {"qu", "去取区"},
    {"quan", "全权泉"},
    {"que", "却确"},
    {"qun", "群"},
    {"ran", "然染"},
    {"rang", "让"},
    {"rao", "绕"},
    {"re", "热"},
    {"ren", "人认任"},
    {"reng", "仍"},
    {"ri", "日"},
    {"rong", "容荣"},
    {"rou", "肉柔"},
    {"ru", "如入"},
    {"ruan", "软"},
    {"rui", "瑞"},
    {"run", "润"},
    {"ruo", "若弱"},
    {"sa", "撒"},
    {"sai", "赛"},
    {"san", "三"},
    {"sang", "桑"},
    {"sao", "扫"},
    {"se", "色"},
    {"sen", "森"},
    {"seng", "僧"},
    {"sha", "沙杀"},
    {"shai", "晒"},
    {"shan", "山善"},
    {"shang", "上商尚"},
    {"shao", "少烧"},
    {"she", "社设舍"},
    {"shei", "谁"},
    {"shen", "什身深神"},
    {"sheng", "生声省升"},
    {"shi", "是时事十实"},
    {"shou", "手受首"},
    {"shu", "书数树"},
    {"shua", "刷"},
    {"shuai", "帅摔"},
    {"shuan", "拴"},
    {"shuang", "双"},
    {"shui", "水谁"},
    {"shun", "顺"},
    {"shuo", "说"},
    {"si", "四思死私"},
    {"song", "送松"},
    {"sou", "搜"},
    {"su", "苏素速"},
    {"suan", "算酸"},
    {"sui", "随岁碎"},
    {"sun", "孙损"},
    {"suo", "所锁"},
    {"ta", "他她它"},
    {"tai", "太台态"},
    {"tan", "谈弹探"},
    {"tang", "堂糖躺"},
    {"tao", "套逃桃"},
    {"te", "特"},
    {"teng", "疼腾"},
    {"ti", "体提题"},
    {"tian", "天田"},
    {"tiao", "条跳调"},
    {"tie", "铁贴"},
    {"ting", "听停庭"},
    {"tong", "同通痛"},
    {"tou", "头投透"},
    {"tu", "图土突"},
    {"tuan", "团"},
    {"tui", "推退"},
    {"tuo", "托脱"},
    {"wa", "哇挖"},
    {"wai", "外"},
    {"wan", "完万晚玩"},
    {"wang", "王往网忘"},
    {"wei", "为位未味"},
    {"wen", "问文温"},
    {"weng", "翁"},
    {"wo", "我"},
    {"wu", "五物无午"},
    {"xi", "西喜系细"},
    {"xia", "下夏"},
    {"xian", "先现线闲"},
    {"xiang", "想向相像"},
    {"xiao", "小笑校消"},
    {"xie", "写些谢"},
    {"xin", "新心信"},
    {"xing", "行性星兴"},
    {"xiong", "兄雄胸"},
    {"xiu", "休修秀"},
    {"xu", "需许续"},
    {"xuan", "选宣"},
    {"xue", "学雪"},
    {"xun", "寻训"},
    {"ya", "呀压牙"},
    {"yan", "眼言研颜"},
    {"yang", "样阳杨养"},
    {"yao", "要药摇"},
    {"ye", "也业夜叶"},
    {"yi", "一以已意"},
    {"yin", "因音银"},
    {"ying", "应影英硬"},
    {"yo", "哟"},
    {"yong", "用永勇"},
    {"you", "有又友右"},
    {"yu", "与于语雨"},
    {"yuan", "元原远院"},
    {"yue", "月越约"},
    {"yun", "云运"},
    {"za", "杂砸"},
    {"zai", "在再"},
    {"zan", "咱赞"},
    {"zang", "脏藏"},
    {"zao", "早造"},
    {"ze", "则责"},
    {"zei", "贼"},
    {"zen", "怎"},
    {"zeng", "曾增"},
    {"zha", "扎炸"},
    {"zhai", "摘窄"},
    {"zhan", "站战展"},
    {"zhang", "长张章"},
    {"zhao", "找照着"},
    {"zhe", "这着者"},
    {"zhen", "真针"},
    {"zheng", "正整争"},
    {"zhi", "知只之直智"},
    {"zhong", "中种重"},
    {"zhou", "周州"},
    {"zhu", "主住注"},
    {"zhua", "抓"},
    {"zhuai", "拽"},
    {"zhuan", "转专"},
    {"zhuang", "装壮"},
    {"zhui", "追"},
    {"zhun", "准"},
    {"zhuo", "桌着"},
    {"zi", "字自子"},
    {"zong", "总宗"},
    {"zou", "走"},
    {"zu", "组足族"},
    {"zuan", "钻"},
    {"zui", "最嘴"},
    {"zun", "尊"},
    {"zuo", "做作坐左"},
};

constexpr char k_digit_letters[][6] = {
    "", "", "abc", "def", "ghi", "jkl", "mno", "pqrs", "tuv", "wxyz",
};

const char *utf8_next(const char *text)
{
    const auto lead = static_cast<unsigned char>(*text);
    if (lead < 0x80U) {
        return text + 1;
    }
    if ((lead & 0xE0U) == 0xC0U) {
        return text + 2;
    }
    if ((lead & 0xF0U) == 0xE0U) {
        return text + 3;
    }
    if ((lead & 0xF8U) == 0xF0U) {
        return text + 4;
    }
    return text + 1;
}

bool already_has_char(const char *out, const char *glyph, size_t glyph_len)
{
    for (const char *cursor = out; *cursor != '\0';) {
        const char *next = utf8_next(cursor);
        const size_t len = static_cast<size_t>(next - cursor);
        if (len == glyph_len && std::memcmp(cursor, glyph, len) == 0) {
            return true;
        }
        cursor = next;
    }
    return false;
}

} // namespace

char t9_digit_for_letter(char letter)
{
    char folded = letter;
    if (folded >= 'A' && folded <= 'Z') {
        folded = static_cast<char>(folded - 'A' + 'a');
    }
    if (folded < 'a' || folded > 'z') {
        return '\0';
    }
    if (folded <= 'c') {
        return '2';
    }
    if (folded <= 'f') {
        return '3';
    }
    if (folded <= 'i') {
        return '4';
    }
    if (folded <= 'l') {
        return '5';
    }
    if (folded <= 'o') {
        return '6';
    }
    if (folded <= 's') {
        return '7';
    }
    if (folded <= 'v') {
        return '8';
    }
    return '9';
}

const char *t9_letters_for_digit(char digit)
{
    if (digit < '0' || digit > '9') {
        return "";
    }
    return k_digit_letters[static_cast<size_t>(digit - '0')];
}

char t9_multitap_letter(char digit, unsigned taps, bool uppercase)
{
    const char *letters = t9_letters_for_digit(digit);
    const size_t count = std::strlen(letters);
    if (count == 0 || taps == 0) {
        return '\0';
    }
    char letter = letters[(taps - 1U) % count];
    if (uppercase && letter >= 'a' && letter <= 'z') {
        letter = static_cast<char>(letter - 'a' + 'A');
    }
    return letter;
}

bool t9_pinyin_matches(const char *pinyin, const char *digits)
{
    if (pinyin == nullptr || digits == nullptr || digits[0] == '\0') {
        return false;
    }
    size_t index = 0;
    for (; digits[index] != '\0'; ++index) {
        if (pinyin[index] == '\0') {
            return false;
        }
        if (t9_digit_for_letter(pinyin[index]) != digits[index]) {
            return false;
        }
    }
    return true;
}

size_t t9_collect_chars(const char *digits, char *out, size_t out_bytes, size_t max_chars)
{
    if (digits == nullptr || out == nullptr || out_bytes == 0 || max_chars == 0) {
        return 0;
    }
    out[0] = '\0';
    size_t written = 0;
    size_t chars = 0;
    for (const auto &entry : k_dict) {
        if (!t9_pinyin_matches(entry.pinyin, digits)) {
            continue;
        }
        for (const char *glyph = entry.chars; *glyph != '\0' && chars < max_chars;) {
            const char *next = utf8_next(glyph);
            const size_t glyph_len = static_cast<size_t>(next - glyph);
            if (already_has_char(out, glyph, glyph_len)) {
                glyph = next;
                continue;
            }
            if (written + glyph_len + 1 >= out_bytes) {
                return chars;
            }
            std::memcpy(out + written, glyph, glyph_len);
            written += glyph_len;
            out[written] = '\0';
            ++chars;
            glyph = next;
        }
        if (chars >= max_chars) {
            break;
        }
    }
    return chars;
}

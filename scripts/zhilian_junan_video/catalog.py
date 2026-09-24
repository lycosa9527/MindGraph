"""Cinematic empty-shot catalog for the 智联均安 Wan 3.0 promo."""

from __future__ import annotations

from typing import NotRequired, TypedDict

from scripts.zhilian_junan_video.intro import INTRO_NEGATIVE, INTRO_SCENES, INTRO_SHELL
from scripts.zhilian_junan_video.speech import SPEECH_NEGATIVE, SPEECH_SCENES, SPEECH_SHELL, SpeechScene
from scripts.zhilian_junan_video.travel import TRAVEL_SCENES, TRAVEL_SHELL, TravelScene


class PromoScene(TypedDict):
    """One silent 16:9 B-roll clip. Text and logos are added in post."""

    id: str
    slug: str
    name: str
    seconds: int
    prompt: str
    source: NotRequired[str]


SHELL = (
    "电影级宣传片质感，ARRI Alexa 65 拍摄，Cooke 电影镜头，24fps，HDR，ACES 电影调色，"
    "深蓝/藏青主色调，暖金高光，北师大红点缀，体积光，丁达尔光，浅景深，轻微胶片颗粒，"
    "高动态范围，超精细，8K，16:9，画面干净，构图高级，留字幕安全区，"
    "无文字，无logo，无水印，无畸变。"
)
NEGATIVE = (
    "文字，乱码，字母，logo，水印，校徽，姓名条，低清，模糊，噪点，过曝，死黑，闪烁，跳帧，"
    "人脸扭曲，多手多脚，肢体变形，塑料感，卡通，动漫，赛博朋克，过饱和，快切，镜头抖动，"
    "夸张特效，廉价感，畸变，鱼眼，杂乱背景。"
)
RESOLUTION = "1080P"
RATIO = "16:9"
DEFAULT_SECONDS = 4

SCENES: tuple[PromoScene, ...] = (
    {
        "id": "00",
        "slug": "studio-bg",
        "name": "数字人演播位背景",
        "seconds": DEFAULT_SECONDS,
        "prompt": (
            "高端学术虚拟演播厅空镜，画面里绝对不能出现任何人、人脸、主播、数字人、手、姓名条、字幕条。"
            "深蓝到藏青渐变空间，后方虚化一座庄严大学主楼剪影与木纹书架，地球仪、合上的书卷、金属装饰，"
            "半透明无字思维导图只有发光节点和连线从地面缓慢生长，神经元粒子与数据光点缓慢流动，"
            "环形LED柔光，暖金轮廓光落在空的中心偏右半身位，左侧大面积留白给后期姓名条，"
            "地面轻微镜面反射，体积光，丁达尔光，镜头极缓慢推近，浅景深，"
            "庄重，权威，前沿，大气，电影级，4K，8K，16:9，"
            "无文字，无logo，无水印，建筑上不要校名。"
        ),
    },
    {
        "id": "01",
        "slug": "campus-dawn",
        "name": "开场空镜·北师大主楼",
        "seconds": DEFAULT_SECONDS,
        "prompt": (
            "清晨金色日出，一座庄严的中国师范大学学术殿堂式主楼空镜，银杏大道，晨雾弥漫，"
            "丁达尔光穿过树梢，灰墙与暖色砖石立面，建筑宏伟安静，"
            "镜头从低角度缓慢升起，无人机航拍缓慢推进，树影与晨光轻微流动，"
            "画面干净大气，历史感与未来感结合，电影级，ARRI Alexa 65，Cooke 镜头，"
            "深蓝天空与暖金晨光，浅景深，体积光，4K，8K，16:9，"
            "无文字，无logo，无水印，不要旗帜，不要校名，不要校徽。"
        ),
    },
    {
        "id": "02",
        "slug": "digital-classroom",
        "name": "政策与教育数字化空镜",
        "seconds": DEFAULT_SECONDS,
        "prompt": (
            "未来智慧课堂，广角电影镜头，教师剪影站在巨幅全息屏幕前，"
            "屏幕上数据流、思维导图、AI模型结构、知识网络缓慢流动，"
            "学生使用平板与智能终端，蓝色科技光效与暖金轮廓光交织，"
            "镜头从宏观全景缓慢横移到微观屏幕细节，体积光，丁达尔光，浅景深，"
            "国际化，现代化，国家战略级，大气震撼，电影级，4K，8K，16:9，"
            "无文字，无logo。"
        ),
    },
    {
        "id": "03",
        "slug": "quote-threshold",
        "name": "金句1·知识门槛与思维高度",
        "seconds": DEFAULT_SECONDS,
        "prompt": (
            "概念大片，深蓝宇宙空间，左侧是知识阶梯、书本、数据墙逐渐下沉、粒子消散，"
            "象征知识门槛降低；右侧是巨大透明大脑、神经元网络、思维导图向上生长，"
            "金色光柱穿透云层，象征思维高度升值，左右形成强烈对比，"
            "镜头从左侧低角度缓慢拉升到右侧高角度，粒子流动，体积光，丁达尔光，"
            "电影级，超现实，震撼，大气，4K，8K，16:9，无文字，无logo。"
        ),
    },
    {
        "id": "04",
        "slug": "quote-teachers",
        "name": "金句2·善用AI的教师",
        "seconds": DEFAULT_SECONDS,
        "prompt": (
            "未来课堂，教师背影或侧影站在智慧讲台前，面前巨大半透明AI全息光屏，"
            "AI以光点、数据流、思维导图、自动生成教案的形式辅助教学，"
            "光屏映亮教师轮廓，镜头缓慢环绕推进，暖金与深蓝交织，"
            "庄重，温暖，坚定，充满希望，电影级，浅景深，体积光，"
            "4K，8K，16:9，无文字，无logo。"
        ),
    },
    {
        "id": "05a",
        "slug": "junan-campus",
        "name": "均安镇校园航拍",
        "seconds": DEFAULT_SECONDS,
        "prompt": (
            "岭南水乡风格的现代化校园航拍，清晨阳光，河涌、榕树、白墙灰瓦与玻璃教学楼结合，"
            "学生有序进入校园，镜头从河面低空拉升到校园全景，缓慢推进，"
            "温暖，大气，舒展，教育现代化，电影级，无人机航拍，体积光，浅景深，"
            "4K，8K，16:9，无文字，无logo。"
        ),
    },
    {
        "id": "05b",
        "slug": "action-plan-desk",
        "name": "三年行动方案桌面特写",
        "seconds": DEFAULT_SECONDS,
        "prompt": (
            "桌面特写，深酒红皮面文件夹与笔记本叠放，钢笔，陶瓷咖啡杯，绿植，暖色灯光，"
            "浅景深，镜头缓慢推近，庄重，正式，学术合作感，电影级，4K，16:9，"
            "无文字，无logo，封皮不要出现可读文字，不要红头文件，不要国徽，不要公章。"
        ),
    },
    {
        "id": "06",
        "slug": "mind-platform",
        "name": "Mind智能教研平台",
        "seconds": DEFAULT_SECONDS,
        "prompt": (
            "高端智能大屏，深蓝色科技UI，中心是思维教研发光节点，"
            "周围连接思维可视化工具、跨校备课、联合教研、小初贯通、学区共同体模块，"
            "地图上多所学校光点连线到均安中心，数据流如星河缓慢流动，全息投影，透明玻璃材质，"
            "镜头从屏幕微距缓慢拉远到全景，蓝色与金色交织，前沿，震撼，未来感，"
            "电影级，4K，8K，16:9，无文字，无logo。"
        ),
    },
    {
        "id": "07",
        "slug": "ai-compare",
        "name": "传统AI与生成式AI对比",
        "seconds": DEFAULT_SECONDS,
        "prompt": (
            "左右分屏对比，左侧传统分析型AI：冷蓝色数据图表、统计曲线、测量网格、分析模型；"
            "右侧生成式AI：温暖金色大模型对话、自动生成教案、思维导图、教研内容、创意文本，"
            "中间一道发光能量箭头连接，镜头缓慢推进，直观，清晰，科技感，电影级，"
            "深蓝与暖金对比，4K，8K，16:9，无文字，无logo。"
        ),
    },
    {
        "id": "08",
        "slug": "signing",
        "name": "签约协议特写",
        "seconds": DEFAULT_SECONDS,
        "prompt": (
            "签约桌特写，红色封皮协议文件，签字笔，桌面绿植，双方桌牌虚化，暖色灯光，"
            "镜头缓慢推近，文件表面有轻微金色光粒升起，形成光脉，"
            "庄重，合作，启动感，浅景深，电影级，4K，8K，16:9，"
            "无文字，无logo，桌牌和封皮不要出现可读文字。"
        ),
    },
    {
        "id": "09a",
        "slug": "seed-teachers",
        "name": "种子教师联合教研",
        "seconds": DEFAULT_SECONDS,
        "prompt": (
            "跨校教师联合教研场景，线上线下混合，大屏中多校连线，白板上有思维导图，"
            "教师围桌讨论，以背影、侧影、手部为主，暖光，积极向上，镜头缓慢横移，"
            "电影级，浅景深，体积光，4K，8K，16:9，无文字，无logo。"
        ),
    },
    {
        "id": "09b",
        "slug": "student-works",
        "name": "学生思维导图作品",
        "seconds": DEFAULT_SECONDS,
        "prompt": (
            "学生手持思维导图作品、彩色便签、课堂展示，阳光明亮，慢动作，充满希望，"
            "以手部与作品特写为主，浅景深，电影级，体积光，4K，8K，16:9，"
            "无文字，无logo，作品上不要出现可读汉字。"
        ),
    },
    {
        "id": "09c",
        "slug": "junan-model",
        "name": "均安模式光网辐射",
        "seconds": DEFAULT_SECONDS,
        "prompt": (
            "城市与校园光网连接，象征均安模式辐射全镇，深蓝夜景与暖金节点，"
            "多所学校光点连成网络，镜头缓慢升高展开，电影级，浅景深，体积光，"
            "4K，8K，16:9，无文字，无logo。"
        ),
    },
    {
        "id": "10",
        "slug": "closing",
        "name": "收束金句与结尾定格",
        "seconds": DEFAULT_SECONDS,
        "prompt": (
            "高端学术虚拟演播厅背景，空镜无人物，深蓝空间，"
            "金色光粒从四周缓慢汇聚到中心，形成柔和光晕，暖金轮廓光，背景虚化，"
            "镜头极缓慢推近，庄重，温暖，大气；最后光效收束，"
            "画面中心左右两侧各留一个标识安全区，画面定格，"
            "电影级，4K，8K，16:9，无文字，无logo。"
        ),
    },
    {
        "id": "t1",
        "slug": "gold-vein",
        "name": "转场·金色数据光脉",
        "seconds": DEFAULT_SECONDS,
        "prompt": (
            "深蓝空间，一道金色数据光脉从北京师范大学主楼轮廓出发，穿越城市与河流，"
            "连接到岭南水乡校园地图，光脉上有粒子、思维导图、代码流缓慢流动，"
            "镜头跟随光脉高速但平稳推进，大气，震撼，电影级，4K，8K，16:9，"
            "无文字，无logo。"
        ),
    },
    {
        "id": "t2",
        "slug": "particle-mindmap",
        "name": "转场·粒子汇聚成思维导图",
        "seconds": DEFAULT_SECONDS,
        "prompt": (
            "深蓝宇宙空间，金色与蓝色粒子从四面八方汇聚，形成巨大透明思维导图，"
            "再散开成数据流，镜头缓慢旋转推进，体积光，丁达尔光，电影级，震撼，"
            "4K，8K，16:9，无文字，无logo。"
        ),
    },
    {
        "id": "t3",
        "slug": "hologram-assemble",
        "name": "转场·全息碎片拼成平台",
        "seconds": DEFAULT_SECONDS,
        "prompt": (
            "透明全息玻璃碎片在空中漂浮，缓慢拼合成大型智能教研平台界面，"
            "深蓝科技UI，金色边框，数据流流动，镜头从碎片微距拉远到全景，"
            "未来感，震撼，电影级，4K，8K，16:9，无文字，无logo。"
        ),
    },
)


AGENT_SECONDS = 5
AGENT_SHELL = (
    "图1和图2只用于锁定同一只2D卡通黄色小龙吉祥物：圆滚滚身体，浅黄皮肤，蓝色腮红，"
    "蓝色学士帽，双手捧一本蓝色小书，书上是灯泡图形而不是文字，尾巴是发光圆点连线。"
    "不要换脸，不要换配色，不要第二个角色，不要写成真人，不要3D写实。"
    "参考图不是成片第一帧，不要把白底证件照接到视频开头。"
    "画面里绝对不要出现任何文字、字母、数字、水印、logo、校徽、字幕。"
)
AGENT_NEGATIVE = (
    "文字，乱码，字母，数字，logo，水印，校徽，姓名条，豆包，低清，模糊，"
    "人脸，真人，换脸，换配色，第二个角色，3D写实，塑料感，过饱和，快切，"
    "镜头抖动，畸变，鱼眼，杂乱背景。"
)
AGENT_SCENES: tuple[PromoScene, ...] = (
    {
        "id": "a1",
        "slug": "recreate",
        "name": "还原·奶油底半身",
        "seconds": AGENT_SECONDS,
        "prompt": (
            "横向16:9，干净浅奶油白背景，同一只黄色小龙吉祥物居中半身，"
            "轻轻呼吸，眨眼，嘴角微笑，蓝色小书微微发光，尾巴节点轻轻闪一下，"
            "镜头极缓慢推近，画面干净，无文字，无水印。"
        ),
    },
    {
        "id": "a2",
        "slug": "studio",
        "name": "学术演播厅",
        "seconds": AGENT_SECONDS,
        "prompt": (
            "横向16:9，同一只黄色小龙站在深蓝学术演播厅，后方虚化书架与主楼剪影，"
            "暖金轮廓光，地面轻反射，无字发光节点在脚下缓慢流动，"
            "镜头极缓慢推近，庄重可爱，无文字，无水印，无姓名条。"
        ),
    },
    {
        "id": "a3",
        "slug": "campus",
        "name": "银杏校园",
        "seconds": AGENT_SECONDS,
        "prompt": (
            "横向16:9，同一只黄色小龙站在清晨银杏大道前景，远处庄严大学主楼虚化，"
            "晨雾与暖金阳光，镜头缓慢升高，画面干净，无旗帜，无校名，无文字，无水印。"
        ),
    },
    {
        "id": "a4",
        "slug": "nodes",
        "name": "无字知识节点",
        "seconds": AGENT_SECONDS,
        "prompt": (
            "横向16:9，同一只黄色小龙捧着发光蓝书，书上只有灯泡图形，"
            "金色与蓝色圆点连线从书页升起，形成无字思维网络，深蓝背景，"
            "镜头缓慢环绕，无文字，无字母，无数字，无水印。"
        ),
    },
)


def _promo_from_travel(item: TravelScene) -> PromoScene:
    return {
        "id": item["id"],
        "slug": item["slug"],
        "name": item["name"],
        "seconds": item["seconds"],
        "prompt": item["prompt"],
        "source": item["source"],
    }


def _travel_plates() -> tuple[PromoScene, ...]:
    return tuple(_promo_from_travel(item) for item in TRAVEL_SCENES)


def _intro_plates() -> tuple[PromoScene, ...]:
    return tuple(_promo_from_travel(item) for item in INTRO_SCENES)


def _promo_from_speech(item: SpeechScene) -> PromoScene:
    return {
        "id": item["id"],
        "slug": item["slug"],
        "name": item["name"],
        "seconds": item["seconds"],
        "prompt": item["prompt"],
    }


def _speech_plates() -> tuple[PromoScene, ...]:
    return tuple(_promo_from_speech(item) for item in SPEECH_SCENES)


def _all_scenes() -> tuple[PromoScene, ...]:
    return SCENES + AGENT_SCENES + _travel_plates() + _intro_plates() + _speech_plates()


def uses_travel(scene: PromoScene) -> bool:
    """Travel clips lock the dragon plus one earlier environment still."""
    return scene["id"].startswith("d")


def uses_intro(scene: PromoScene) -> bool:
    """Spoken 20s self-intro plates for 均安起思楼."""
    return scene["id"].startswith("i")


def uses_speech(scene: PromoScene) -> bool:
    """Silent 8s cinematic plates timed to 纯演讲稿_v2.mp4."""
    return scene["id"].startswith("s")


def uses_agent(scene: PromoScene) -> bool:
    """Dragon-locked clips, including travel and intro plates."""
    return scene["id"].startswith("a") or uses_travel(scene) or uses_intro(scene)


def scene_by_id(scene_id: str) -> PromoScene:
    """Look up a scene by 00, 00-studio-bg, a1, or d01-campus-walk."""
    needle = scene_id.strip()
    for scene in _all_scenes():
        packed = f"{scene['id']}-{scene['slug']}"
        if needle in (scene["id"], packed):
            return scene
    raise ValueError(f"Unknown promo scene: {scene_id}")


def select_scenes(
    raw_ids: str | None,
    *,
    agent: bool = False,
    travel: bool = False,
    intro: bool = False,
    speech: bool = False,
) -> list[PromoScene]:
    """Return empty shots, dragon plates, travel plates, intros, speech, or requested ids."""
    if raw_ids:
        return [scene_by_id(item.strip()) for item in raw_ids.split(",") if item.strip()]
    if speech:
        return list(_speech_plates())
    if intro:
        return list(_intro_plates())
    if travel:
        return list(_travel_plates())
    if agent:
        return list(AGENT_SCENES)
    return list(SCENES)


def environment_source(scene: PromoScene) -> str:
    """Empty-shot filename locked as figure 3 for a travel plate."""
    source = scene.get("source")
    if not source:
        raise ValueError(f"{scene['id']} has no environment source")
    return source


def clip_stem(scene: PromoScene) -> str:
    """Work-dir filename without suffix."""
    return f"{scene['id']}-{scene['slug']}"


def clip_prompt(scene: PromoScene) -> str:
    """Scene prompt plus the matching cinematic or dragon-lock suffix."""
    if uses_intro(scene):
        return f"{INTRO_SHELL}{scene['prompt']}不要出现：{INTRO_NEGATIVE}"
    if uses_speech(scene):
        return f"{SPEECH_SHELL}{scene['prompt']}不要出现：{SPEECH_NEGATIVE}"
    if uses_travel(scene):
        return f"{TRAVEL_SHELL}{scene['prompt']}不要出现：{AGENT_NEGATIVE}"
    if uses_agent(scene):
        return f"{AGENT_SHELL}{scene['prompt']}不要出现：{AGENT_NEGATIVE}"
    return f"{scene['prompt']}{SHELL}不要出现：{NEGATIVE}"

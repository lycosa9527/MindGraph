"""October-update promo. Mouths stay closed. Screenshots are pinned on later."""

from __future__ import annotations

from typing import TypedDict

from scripts.sync_classroom_video.roles import RoleStill, identity_shell

RESOLUTION = "1080P"
RATIO = "16:9"
FUN_MUSIC = "fun-music-v1"
Crop = tuple[float, float, float, float]
SET_LOCK = (
    "横向16:9，1080P，30fps，3D动画电影质感。"
    "极简北师大教室：环形木桌、侧窗、前方墙上一块绿幕黑板。"
    "绿幕黑板钉在教室前方墙面的同一位置，七段都是这一块："
    "不能换墙，不能挪位，不能旋转，不能消失，不能换成另一块屏幕。"
    "黑板在墙上的尺寸不变，但镜头可以推近，所以它在画面里可以略变大。"
    "黑板始终留在画面中上部，正面朝向镜头，四边平直，约占画面宽度的一半以上，不能出画。"
    "镜头可以推近、拉远或轻横移，但要很慢。不要环绕到黑板侧面，不要让黑板离开画面。"
    "黑板内壁是均匀的亮绿色幕，干净纯绿，颜色饱和，没有字，没有线条，没有纹理，没有粉笔灰，"
    "没有反光，没有图标，没有窗口。木框可以留着。"
    "角色、衣服、眼睛和窗外不要使用同样的亮绿色。"
    "角色可以指向黑板、在它前面表演，身体不要踏进绿色区域，绿色要整块留白。"
    "五个角色必须同时在场：雪纳瑞导师、黑猫、白猫、戴眼镜的暹罗猫、乌鸦。"
    "不要人类身体，不要换脸，不要换毛色，不要合并角色。"
    "角色不开口，嘴始终闭合。无对白，无字幕，无歌词，无哼唱。"
    "纸面和报纸保持空白。界面留给后期替换，不要画进绿幕。"
)
CONTINUITY = (
    "七段是同一间教室里的一条连续表演，后期会按01到07首尾相接。"
    "不要片头，不要黑场，不要淡入淡出，不要字幕卡，不要重新介绍教室和角色。"
    "绿幕黑板一直钉在前方墙的同一处，并且一直留在画面里，只有镜头在缓慢移动。"
    "光线、桌椅和站位从这段的承接动作接着演，结尾停在能接下一秒的姿势上。"
)
SOUND_LOCK = (
    "音轨只有肢体和物件音效：脚步、粉笔、纸张、轻敲、滑稽撞击。"
    "不要人声，不要口播，不要歌词，不要哼唱，不要口哨，不要掌声。"
)
NEGATIVE = (
    "人声,口播,对白,歌词,哼唱,口哨,字幕,可读文字,汉字,英文字母,logo,水印,UI,图标,按钮,"
    "绿幕上的图形,绿幕上的光,绿幕上的窗口,画在白板上的线,节点图,脉冲光,截图,界面窗口,"
    "黑板挪位,黑板换墙,两块绿幕,黑板变形,黑板消失,黑板出画,侧面黑板,粉笔灰,黑板纹理,"
    "开口说话,人类身体,真人,换脸,换毛色,参考静帧,证件照,全身站立开场,掌声,黑场,淡出,"
    "vocals, lyrics, spoken words, dialogue, subtitles, humming, whistling, "
    "dark, horror, EDM, applause, crowd noise"
)
BGM_PROMPT = (
    "Instrumental cinematic silent-comedy score for a product update reveal. "
    "Playful, quirky, techy, warm, jazzy, mischievous, and finally uplifting. "
    "No vocals, no lyrics, no spoken words, no humming, no whistling. "
    "Around 2:20-2:30, 120-132 BPM. Instruments: pizzicato strings, marimba, "
    "clarinet, bassoon, muted trumpet, upright bass, brushed jazz drums, piano, "
    "glockenspiel, celesta, harp glissando, woodblock, castanets, light cymbal swells, "
    "soft synth pulses, digital chimes. Structure: curious classroom discussion intro; "
    "sneaky game-costume chase with stop-start brass and fast pizzicato; clumsy fall "
    "and magical pulse for the October update; bright feature-showcase montage with "
    "woodblock, chimes and playful synth ticks; warm ascending strings for teamwork; "
    "joyful final button ending. Light, witty, cinematic, elegant, clear dynamic contrast. "
    "No dark, horror, heavy, sad, epic trailer or EDM mood. "
    "Musical comedic hits only, not literal sound effects."
)


class PromoClip(TypedDict):
    """One closed-mouth beat. The screenshot pan is applied after Wan."""

    id: str
    slug: str
    name: str
    seconds: int
    link: str
    prompt: str
    sfx: str
    overlay: str
    speech: str
    crops: tuple[Crop, ...]


CLIPS: tuple[PromoClip, ...] = (
    {
        "id": "01",
        "slug": "new-canvas",
        "name": "新画布",
        "seconds": 22,
        "link": "镜头从教室后方缓慢推近这块固定的绿幕黑板，黑板一直留在画面里。结束时五人都看向黑板。",
        "prompt": (
            "导师站在黑板左侧，先向大家张开手，再沿黑板顶边的空气点过去，像介绍上面一排工具，"
            "然后指向黑板下沿，教鞭不碰到板面。"
            "白猫坐在左侧，拿两张空白卡片，从一张刷到另一张，表情认真。"
            "暹罗猫举起两张空白卡，把后面那张换到前面，再把旧卡收到桌下，看导师。"
            "乌鸦把一叠空白纸揭开一页又盖回去，冷静点头。"
            "黑猫举粉笔冲向绿幕，白猫用报纸卷敲桌。黑猫缩回，改在黑板下方的空气里划一条短线，得意看大家。"
            "绿色区域没有字。无对白无文字无字幕，嘴闭合。"
        ),
        "sfx": "音效：教鞭点空气、卡片轻刷、翻纸、报纸敲桌。",
        "overlay": "01.png 从全图推到功能区，再落到状态栏。",
        "speech": (
            "各位老师，大家好。欢迎来到迈特平台的十月更新。"
            "这个月，一打开思维导图，就是这张新画布。功能区在上面，格式刷、历史版本都在手边。"
            "底下只留一行状态栏。经典画布还在，收到语言设置里了。"
        ),
        "crops": ((0.0, 0.0, 1.0, 1.0), (0.04, 0.0, 0.92, 0.46), (0.0, 0.42, 1.0, 0.58)),
    },
    {
        "id": "02",
        "slug": "branch-level",
        "name": "编号和程度",
        "seconds": 22,
        "link": "紧接上一段，黑板还在画面里的原位。结束时导师教鞭停在卡片外侧，黑猫爪子收回。",
        "prompt": (
            "中景轻横移。导师用教鞭在空白卡片旁边的空气里点出层级，不写到卡片文字上，也不写到黑板上。"
            "白猫把黑猫的爪子从卡片中间拨到卡片外侧，摇头。黑猫又往字上戳，被白猫按住，耳朵压平。"
            "暹罗猫转动桌上的旋钮，头顶气泡从简单变成复杂，然后把动作放慢。"
            "乌鸦跟着把翅膀放慢，点头。"
            "黑猫只对着导师点到的那一张卡做小动作，不碰旁边的卡。"
            "绿色区域没有字。无对白无文字无字幕，嘴闭合。"
        ),
        "sfx": "音效：教鞭点三下、爪子被拨开、旋钮咔嗒、动作变慢。",
        "overlay": "02.png 从右侧编号横移到左侧，再落到专业程度。",
        "speech": (
            "分支可以编号了。您看，一、一点一，标在节点外面，不写进文字里。"
            "专业程度定在底部这一行。往后生成、展开、头脑风暴、做摘要、讲节点，还有 Kitty，都按您选的这个程度来。"
        ),
        "crops": ((0.50, 0.22, 0.48, 0.52), (0.02, 0.22, 0.48, 0.52), (0.08, 0.62, 0.84, 0.36)),
    },
    {
        "id": "03",
        "slug": "gestures-share",
        "name": "概要和关联",
        "seconds": 22,
        "link": "紧接上一段，人还在同一块黑板前。结束时黑猫被翅膀挡开，钥匙仍在乌鸦手里。",
        "prompt": (
            "导师双手比一个大括号，把两张空白卡收成一组，不碰到黑板。"
            "白猫在两张卡之间拉一条虚线毛线，退后看。"
            "暹罗猫往一张卡上挂小图标、小链环和空白小相框，不挂到黑板上。"
            "黑猫用粉笔把一张卡斜划下桌，再在旁边补一张，又在下面垫一张更小的。"
            "白猫对着空气双指张开，再多指收回。"
            "乌鸦独自整理同一叠空白纸，翅膀里攥着一把小钥匙。白猫和暹罗猫只看着，不伸手。"
            "黑猫去抢钥匙，被乌鸦翅膀挡开，缩脖。"
            "绿色区域没有字。无对白无文字无字幕，嘴闭合。"
        ),
        "sfx": "音效：毛线拉紧、卡片斜划落地、钥匙轻响、翅膀挡开。",
        "overlay": "03.png 从关联虚线落到概要括号。",
        "speech": (
            "这个括号是概要，把一整支收在一起。虚线是关联，分开的节点还能连上。"
            "图标、链接和图片，都可以挂在节点上。斜划一下，就能删，能加兄弟，也能加子节点。大屏上可以捏合。"
            "导出是矢量图。学习单的空，还留在原来的位置。"
            "校内一起看一张图：谁先打开，谁来改，其他人看的是同一张。人工智能，只有主人能用。"
        ),
        "crops": ((0.22, 0.02, 0.62, 0.46), (0.04, 0.36, 0.92, 0.58)),
    },
    {
        "id": "04",
        "slug": "quick-talk",
        "name": "回到首页",
        "seconds": 22,
        "link": "紧接上一段的座位。结束时乌鸦把黑猫按回座位，白猫仍面向黑板。",
        "prompt": (
            "导师先合着一本大书摇头。暹罗猫从桌侧翻开一排形状不同的空白卡，点一下就摊开，不用等待。"
            "导师这才把书打开，指向其中一张卡。"
            "黑猫被那排卡吓得后仰，爪子乱挥，暹罗猫扶住他。"
            "白猫面向绿幕黑板做演讲姿势，手里托一条空白纸条，纸条不贴到黑板上。"
            "黑猫在角落模仿演讲，乌鸦用翅膀把他按回座位。钥匙还在乌鸦翅膀里。"
            "绿色区域没有字。无对白无文字无字幕，嘴闭合。"
        ),
        "sfx": "音效：书本打开、卡片摊开、椅子后仰、翅膀按回座位。",
        "overlay": "04.png 从图示墙推到左侧快速访问。",
        "speech": (
            "回到首页。左边是快速访问，八大思维图示点开就能用，不用再干等模型。"
            "图存好了，可以全屏讲。编辑器也不再一进平台就下载，真正打开一张图，才开始加载。"
        ),
        "crops": ((0.26, 0.16, 0.72, 0.74), (0.0, 0.18, 0.55, 0.70)),
    },
    {
        "id": "05",
        "slug": "teaching",
        "name": "思维讲堂",
        "seconds": 22,
        "link": "紧接上一段的座位，镜头沿桌边轻横移。结束时黑猫坐直，白猫叹气，暹罗猫憋笑，乌鸦摇头。",
        "prompt": (
            "导师沿桌边走，教鞭顺着一排卡片里的一支点过去。白猫、暹罗猫、乌鸦一起把身体倾向那一支。"
            "白猫端正坐好。暹罗猫掏出手机，屏幕背对镜头，做三个手势：点一下、放开、往回拉。"
            "乌鸦展开一条空白长纸。黑猫拿着小点击器对着那条纸按，差点摔倒，抓住桌沿。"
            "白猫把一叠空白图像卡排开。乌鸦再举起一叠空白纸，像要装订。"
            "导师回头。黑猫坐直装认真。白猫叹气，暹罗猫憋笑，乌鸦摇头。"
            "绿色区域没有字，不要在板上发光。无对白无文字无字幕，嘴闭合。"
        ),
        "sfx": "音效：稳健脚步、手机轻点、长纸展开、点击器、抓桌沿。",
        "overlay": "05.png 推近思维讲堂对话框。",
        "speech": (
            "讲给学生听，就打开思维讲堂。选画布语音巡讲，按主分支往下走，整条分支都会亮。语气可以用课堂。"
            "同一张图，还能带到校本培训里。手机上开始、自由或者拉取，提词器和点击器都跟着。"
            "学习空间的作业按学校分开。智绘把它收成一叠课图。教学设计可以导出 Word，用学校自己的模板。"
        ),
        "crops": ((0.08, 0.04, 0.84, 0.92), (0.24, 0.10, 0.52, 0.78)),
    },
    {
        "id": "06",
        "slug": "rooms-login",
        "name": "讲到这一处",
        "seconds": 20,
        "link": "紧接上一段的桌边，镜头再近一点，黑板仍在画面里。结束时乌鸦挡住黑猫，黑猫耳朵压平。",
        "prompt": (
            "桌边中近景。导师只指向桌上的一张卡。"
            "白猫把一张小空白引用卡和两张空白图片放在这一张卡旁边，不放到别的卡上。"
            "黑猫只摸这一张卡，爪子离开后不再碰其他卡，嘴巴紧闭。"
            "暹罗猫按住手腕上的小手表，对着这一张卡点头。"
            "乌鸦把小纸条排成一列，在一条后面点一下，再把一张纸条放到白猫面前。纸上没有字。"
            "乌鸦看手机背面，再指向黑板下方的空气。不要出现二维码，不要在黑板上画开关。"
            "黑猫想抢手表，被乌鸦翅膀挡开，耳朵压平。"
            "绿色区域没有字。无对白无文字无字幕，嘴闭合。"
        ),
        "sfx": "音效：只点一张卡、手表轻点、纸条入列、翅膀挡开。没有说话声。",
        "overlay": "06.png 从节点移到讲解出处，再移到配图。",
        "speech": (
            "点开一个节点，讲解就停在这里。思考完，段落里有出处，旁边配上图。"
            "Kitty 只改您点到的地方。语音笔记分得出是谁在说，可以改名、合并，下次接着讲。"
            "手表按住，就能对着这张图说。"
            "研讨按顺序送到，也能看见谁读了。研习社还是本校的，私信写着对方的名字。"
            "登录可以微信扫码。侧边栏，一直是这所学校的名字。"
        ),
        "crops": ((0.0, 0.10, 0.46, 0.78), (0.16, 0.04, 0.40, 0.80), (0.50, 0.02, 0.50, 0.86)),
    },
    {
        "id": "07",
        "slug": "finale",
        "name": "收",
        "seconds": 15,
        "link": "紧接上一段，镜头从桌边缓慢拉远。不要定格，不要在黑板上发光。黑板仍留在画面里。",
        "prompt": (
            "导师在桌上摊开几种形状不同的空白卡，请大家选。"
            "白猫、暹罗猫、乌鸦同时看向绿幕黑板，身体前倾。导师抱臂，满意点头。"
            "黑猫在空白纸上画一个圈，再指向黑板，尾巴高竖，兴奋绕桌跑半圈。"
            "白猫用报纸卷轻敲一下，黑猫笑着跳回座位。"
            "五人一起看向黑板。不要贴标志，不要定格。"
            "绿色区域没有字。无对白无文字无字幕，嘴闭合。"
        ),
        "sfx": "音效：纸上画圈、报纸轻敲、绕桌脚步，最后一下明亮的收束音。",
        "overlay": "07.png 从一张图示拉远到整个首页。",
        "speech": (
            "各位老师，回到首页，选一种图，就可以开始。一张图，从画到讲，从讲到课。十月的更新，都在迈特平台上。谢谢。"
        ),
        "crops": ((0.16, 0.48, 0.42, 0.42), (0.0, 0.0, 1.0, 1.0)),
    },
)


def clip_by_id(clip_id: str) -> PromoClip:
    """Look up 01 or 01-new-canvas."""
    needle = clip_id.strip()
    for clip in CLIPS:
        packed = f"{clip['id']}-{clip['slug']}"
        if needle in (clip["id"], packed):
            return clip
    raise ValueError(f"Unknown promo clip: {clip_id}")


def select_clips(raw_ids: str | None) -> list[PromoClip]:
    """Parse comma ids, or return the full promo."""
    if not raw_ids:
        return list(CLIPS)
    return [clip_by_id(item.strip()) for item in raw_ids.split(",") if item.strip()]


def clip_stem(clip: PromoClip) -> str:
    """Filename without suffix."""
    return f"{clip['id']}-{clip['slug']}"


def total_seconds() -> int:
    """Sum of the seven beats."""
    return sum(clip["seconds"] for clip in CLIPS)


def clip_prompt(clip: PromoClip, roles: list[RoleStill]) -> str:
    """Identity lock, closed mouths, one beat, and foley. No sung bed."""
    return (
        f"{identity_shell(roles)}{SET_LOCK}{CONTINUITY}{clip['link']}{clip['prompt']}"
        f"{clip['sfx']}{SOUND_LOCK}不要出现：{NEGATIVE}"
    )


def overlay_sheet() -> str:
    """Later composite list. These stay off the Wan frames."""
    lines = ["绿幕后期贴真实截图，不要让 Wan 生成这些 UI。", ""]
    for clip in CLIPS:
        lines.append(f"{clip['id']} {clip['name']}")
        lines.append(clip["overlay"])
        lines.append("")
    return "\n".join(lines)

"""
Bot Discord MA SÓI (discord.py >= 2.3)
- Ban đêm: server-mute toàn bộ người sống, sáng mới mở mic.
- Người chết: chuyển sang kênh thoại "Void Âm Phủ", tách riêng với người sống.
- Đủ 36 vai trò (Dân Làng / Ma Sói / Trung Lập) + phân bổ vai trò động.
Chạy:  DISCORD_TOKEN=xxx python maso_bot.py
"""
import asyncio, os, random, tempfile, time, traceback
from collections import defaultdict

import discord
from discord import app_commands
from discord.ext import commands

# ============================ CẤU HÌNH ============================
NIGHT_SECS = int(os.getenv("NIGHT_SECS", 60))   # tối đa cho giai đoạn đêm
LATE_SECS = int(os.getenv("LATE_SECS", 25))     # giai đoạn "đêm sắp kết thúc" (Phù Thủy / Thầy Đồng)
DAY_SECS = int(os.getenv("DAY_SECS", 120))      # thảo luận ban ngày
VOTE_SECS = int(os.getenv("VOTE_SECS", 45))     # biểu quyết treo cổ
MIN_SECS = 12                                    # đêm tối thiểu (tránh lộ ai có chức năng)
VOICE_MASK = os.getenv("VOICE_MASK", "off")      # "tts": mic khóa cả ngày, bot đọc chữ bằng 1 giọng chung | "off": mở mic ban ngày
TTS_VOICE = os.getenv("TTS_VOICE", "vi-VN-HoaiMyNeural")  # hoặc vi-VN-NamMinhNeural
MIN_PLAYERS = int(os.getenv("MIN_PLAYERS", 5))
MAX_PLAYERS = 30

V, W, N = "V", "W", "N"
PHE = {V: "Thiện 😇 (Dân Làng)", W: "Ác 😈 (Ma Sói)", N: "Trung Lập ⚖️"}
COLOR = {V: 0x57F287, W: 0xED4245, N: 0x99AAB5}

# ============================ VAI TRÒ ============================
ROLES = {
    # ---- Dân Làng ----
    "tientri": ("Tiên Tri", "🔮", V, "Mỗi đêm soi 1 người để biết chính xác họ thuộc phe Ma Sói hay Dân Làng."),
    "baove": ("Bảo Vệ", "🛡️", V, "Mỗi đêm bảo vệ 1 người khỏi Ma Sói. Không bảo vệ cùng 1 người 2 đêm liên tiếp. Được tự bảo vệ."),
    "phuthuy": ("Phù Thủy", "🧪", V, "2 bình thuốc (mỗi bình 1 lần/ván): Cứu sống nạn nhân bị Sói cắn, Độc giết 1 người. Dùng khi đêm sắp kết thúc."),
    "truonglang": ("Trưởng Làng", "👑", V, "Phiếu treo cổ ban ngày tính gấp đôi (x2)."),
    "gialang": ("Già Làng", "👴", V, "Có 2 mạng: lần đầu bị Ma Sói cắn bạn không chết."),
    "bansoi": ("Bán Sói", "🌗", V, "Thuộc Dân Làng. Nếu bị Sói cắn, bạn không chết mà biến thành Ma Sói từ đêm sau. Tiên Tri soi bạn luôn ra Sói."),
    "tinhyeu": ("Thần Tình Yêu", "💘", V, "Đêm đầu chọn 2 người kết đôi. Một người chết vì bất kỳ lý do gì, người kia chết theo."),
    "thosan": ("Thợ Săn", "🏹", V, "1 phát súng duy nhất: chủ động bắn ban đêm, hoặc khi chết (nếu chưa bắn) được bắn kéo theo 1 người."),
    "danlang": ("Dân Làng", "🧑‍🌾", V, "Ban đêm ngủ. Ban ngày thảo luận và biểu quyết treo cổ kẻ khả nghi."),
    "musu": ("Mục Sư", "✝️", V, "Đêm vẩy nước thánh lên 1 người: là Sói thì Sói chết, là người vô tội thì bạn hy sinh."),
    "thamtu": ("Thám Tử", "🕵️", V, "Mỗi đêm chọn 2 người, biết họ CÙNG PHE hay KHÁC PHE."),
    "ngoaicam": ("Nhà Ngoại Cảm", "🔭", V, "Mỗi đêm chọn 2 người. Sáng hôm sau biết 1 trong 2 người có thực hiện hành động giết người đêm qua không."),
    "hoabenho": ("Hoa Bé Nhỏ", "🌸", V, "Ban ngày dùng nút kỹ năng chọn 1 người miễn nhiễm treo cổ hôm đó (1 lần/ván)."),
    "thoren": ("Thợ Rèn", "🔨", V, "Đêm rèn 2 Khiên (chống cắn) và 1 Kiếm (giết người). Mỗi món rèn mất 1 đêm và phải trao cho người khác trước khi rèn tiếp."),
    "thaydong": ("Thầy Đồng", "🪄", V, "Đêm vào Âm Giới chat ẩn danh với người chết. 1 lần/ván hồi sinh 1 linh hồn NGẪU NHIÊN (có thể cả Sói) khi đêm kết thúc."),
    # ---- Ma Sói ----
    "masoi": ("Ma Sói", "🐺", W, "Mỗi đêm cùng bầy cắn 1 người. Thắng khi số Sói ≥ số Dân Làng còn sống."),
    "doaudan": ("Sói Đầu Đàn", "👹", W, "Cùng bầy cắn người, phiếu cắn tính x2."),
    "soicon": ("Sói Con", "🐶", W, "Nếu bạn chết, đêm sau bầy Sói nổi thịnh nộ và cắn cùng lúc 2 người!"),
    "soitientri": ("Sói Tiên Tri", "🔮", W, "Không cắn được khi còn vai này. Mỗi đêm soi vai trò chính xác của 1 người (chia sẻ cho bầy). Bấm 'Hóa Sói Thường' để cắn; tự hóa nếu là Sói duy nhất."),
    "soiacmong": ("Sói Ác Mộng", "😱", W, "Ban ngày ru 1 người vào Cơn Ác Mộng: vô hiệu kỹ năng đêm sau của họ (2 lần/ván)."),
    "soidiencuong": ("Sói Điên Cuồng", "🔥", W, "Ban ngày kích hoạt Điên Cuồng cho đêm sau: cắn xuyên bảo vệ; con mồi được bảo vệ thì cả hai cùng chết (1 lần/ván)."),
    "kephanboi": ("Kẻ Phản Bội", "🗡️", W, "Phe Sói nhưng ẩn danh, chưa cắn được. Tiên Tri soi ra Dân Làng. Khi mọi Sói thật chết, bạn thức tỉnh thành Sói."),
    "soibaoho": ("Sói Bảo Hộ", "🐺🛡️", W, "Ban ngày chọn 1 người (kể cả Sói) miễn nhiễm hoàn toàn treo cổ hôm đó (1 lần/ván)."),
    "soitre": ("Sói Trẻ", "🍼", W, "Đêm 1 chọn 1 người gắn bó sinh tử: bạn chết thì họ chết theo."),
    "soimeocon": ("Sói Mèo Con", "🐱", W, "1 lần/ván biến 1 người thành Sói (chỉ thành công nếu là Dân Làng và không được bảo vệ)."),
    "soiphantach": ("Sói Phân Tách", "⛓️", W, "Ràng buộc 1 người: tính là 2 Sói khi xét thắng. Bạn chết → họ chết. Họ chết → vai trò của bạn bị lộ."),
    "soiphaohoa": ("Sói Pháo Hoa", "🎆", W, "Mỗi đêm không ai bị Sói cắn chết tích 1 pháo hoa (tối đa 2). Ban ngày đốt để giết ngay số người tương ứng (bị lộ danh tính)."),
    # ---- Trung Lập ----
    "kebatchuoc": ("Kẻ Bắt Chước", "🎭", N, "Đêm 1 chọn 1 người đối bóng. Khi họ chết bạn nhận vai trò + phe của họ."),
    "daophu": ("Đao Phủ", "🪓", N, "Có mục tiêu bí mật. Thắng ngay khi mục tiêu bị treo cổ!"),
    "thangngo": ("Thằng Ngố", "🤡", N, "Thắng ngay nếu bị dân làng treo cổ ban ngày."),
    "satnhan": ("Sát Nhân Hàng Loạt", "🔪", N, "Mỗi đêm giết 1 người. Thắng khi là người duy nhất sống sót."),
    "anthit": ("Kẻ Ăn Thịt Người", "🍖", N, "Mỗi đêm nuốt 1 người HOẶC nhịn đói để ăn bù (tối đa 5 người/đêm). Không bị Sói cắn chết. Thắng khi là người cuối cùng."),
    "giaochu": ("Giáo Chủ", "🌀", N, "Mỗi đêm thu phục 1 người vào Giáo Phái. Giáo Chủ chết thì cả Giáo Phái chết. Thắng khi mọi người sống đều thuộc Giáo Phái."),
}
VPOOL = ["tientri", "baove", "phuthuy", "truonglang", "gialang", "bansoi", "tinhyeu", "thosan",
         "musu", "thamtu", "ngoaicam", "hoabenho", "thoren", "thaydong"]
NPOOL = ["thangngo", "satnhan", "daophu", "kebatchuoc", "anthit", "giaochu"]
WFUNC = [k for k, v in ROLES.items() if v[2] == W and k != "masoi"]
LOCK = {"seer", "detective", "wseer", "give"}  # kỹ năng chỉ dùng 1 lần/đêm (không đổi ý)


def build_roles(n):
    """Phân bổ vai trò động theo số người chơi."""
    if n <= 7:
        wolves = [random.choice(["masoi"] + [k for k in WFUNC if k != "kephanboi"])]
        neu, core, sp, pool = 1, [], random.randint(1, 2), list(VPOOL)
    else:
        w = 2 if n <= 11 else 3 if n <= 15 else max(4, round(n * 0.25))
        funcs = random.sample(WFUNC, min(w - 1, len(WFUNC)))
        wolves = ["masoi"] + funcs + ["masoi"] * (w - 1 - len(funcs))
        neu = 1 if n <= 11 else (random.randint(1, 2) if n <= 15 else 2)
        core = ["tientri", "baove", "phuthuy"]
        sp = random.randint(1, 3) if n <= 11 else random.randint(4, 6) if n <= 15 else random.randint(7, 9)
        pool = [k for k in VPOOL if k not in core]
    sp = max(0, min(sp, n - len(wolves) - neu - len(core)))
    roles = wolves + random.sample(NPOOL, neu) + core + random.sample(pool, sp)
    roles += ["danlang"] * (n - len(roles))
    return roles


class P:
    def __init__(self, m, role):
        self.m, self.id = m, m.id
        self.real = self.name = m.display_name  # name = nhãn ẩn danh trong ván, real = tên thật
        self.alive, self.inbox = True, []
        self.lover, self.cult = None, False
        self.dis = self.nm_next = self.convert_next = self.exposed = False
        self.shield, self.sword = 0, False
        self.set_role(role)

    def set_role(self, role):
        self.role, self.team, self.s = role, ROLES[role][2], defaultdict(int)
        if role == "gialang": self.s["lives"] = 2
        if role == "phuthuy": self.s["heal"] = self.s["poison"] = 1
        if role == "thaydong": self.s["rev"] = 1
        if role == "soiacmong": self.s["left"] = 2


GAMES = {}
ANON_NICK = "👻 Linh hồn"


# ============================ UI ============================
class SkillSelect(discord.ui.UserSelect):
    def __init__(self, game, p, key, ph, mn, mx):
        super().__init__(placeholder=ph, min_values=mn, max_values=mx)
        self.game, self.p, self.key = game, p, key

    async def callback(self, i):
        await self.game.on_pick(i, self.p, self.key, [u.id for u in self.values])


class SkillButton(discord.ui.Button):
    def __init__(self, game, p, key, label):
        super().__init__(label=label, style=discord.ButtonStyle.secondary)
        self.game, self.p, self.key = game, p, key

    async def callback(self, i):
        await self.game.on_button(i, self.p, self.key)


class OpenView(discord.ui.View):
    def __init__(self, game):
        super().__init__(timeout=None)
        self.game = game

    @discord.ui.button(label="Xem vai trò / Dùng kỹ năng", emoji="🎭", style=discord.ButtonStyle.primary)
    async def menu(self, i, b):
        await self.game.open_menu(i)

    @discord.ui.button(label="Chat Âm Giới", emoji="👻", style=discord.ButtonStyle.secondary)
    async def chat(self, i, b):
        await self.game.open_chat(i)


class ChatModal(discord.ui.Modal, title="Chat Âm Giới (ẩn danh)"):
    msg = discord.ui.TextInput(label="Tin nhắn", max_length=300)

    def __init__(self, game):
        super().__init__()
        self.game = game

    async def on_submit(self, i):
        p = self.game.players.get(i.user.id)
        if not p or not self.game.can_void_chat(p):
            return await i.response.send_message("Bạn không thể chat Âm Giới lúc này.", ephemeral=True)
        await i.response.send_message("👻 Đã gửi (ẩn danh).", ephemeral=True)
        await self.game.void_say(p.id, self.msg.value)


class VoteView(discord.ui.View):
    def __init__(self, game):
        super().__init__(timeout=None)
        self.game = game
        sel = discord.ui.UserSelect(placeholder="🗳️ Chọn người treo cổ", min_values=1, max_values=1)

        async def cb(i):
            await game.cast(i, sel.values[0].id)
        sel.callback = cb
        self.add_item(sel)

    @discord.ui.button(label="Bỏ qua", emoji="⏭️", style=discord.ButtonStyle.secondary)
    async def skip(self, i, b):
        await self.game.cast(i, None)


class Lobby(discord.ui.View):
    def __init__(self, host, vc):
        super().__init__(timeout=900)
        self.host, self.vc = host, vc
        self.members = {host.id: host}

    def embed(self):
        e = discord.Embed(title="🐺 MA SÓI — Phòng chờ", color=0xF1C40F)
        e.description = (f"Kênh làng: {self.vc.mention}\nChủ phòng: {self.host.mention}\n"
                         f"Cần {MIN_PLAYERS}–{MAX_PLAYERS} người. **Vào kênh thoại trước khi bắt đầu!**")
        e.add_field(name=f"Người chơi ({len(self.members)})",
                    value="\n".join(m.mention for m in self.members.values())[:1000] or "-")
        return e

    @discord.ui.button(label="Tham gia", emoji="✅", style=discord.ButtonStyle.success)
    async def join(self, i, b):
        if len(self.members) >= MAX_PLAYERS:
            return await i.response.send_message("Phòng đã đầy.", ephemeral=True)
        self.members[i.user.id] = i.user
        await i.response.edit_message(embed=self.embed())

    @discord.ui.button(label="Rời", emoji="🚪", style=discord.ButtonStyle.secondary)
    async def leave(self, i, b):
        if i.user.id == self.host.id:
            return await i.response.send_message("Chủ phòng không thể rời.", ephemeral=True)
        self.members.pop(i.user.id, None)
        await i.response.edit_message(embed=self.embed())

    @discord.ui.button(label="Bắt đầu", emoji="▶️", style=discord.ButtonStyle.primary)
    async def start(self, i, b):
        if i.user.id != self.host.id:
            return await i.response.send_message("Chỉ chủ phòng được bắt đầu.", ephemeral=True)
        if len(self.members) < MIN_PLAYERS:
            return await i.response.send_message(f"Cần tối thiểu {MIN_PLAYERS} người.", ephemeral=True)
        if i.guild.id in GAMES:
            return await i.response.send_message("Đang có ván khác.", ephemeral=True)
        self.stop()
        await i.response.edit_message(content="Đang khởi tạo ván...", embed=None, view=None)
        g = Game(i.guild, i.channel, self.vc, self.host, list(self.members.values()))
        GAMES[i.guild.id] = g
        asyncio.create_task(g.run())


# ============================ GAME ============================
class Game:
    def __init__(self, guild, text, vc, host, members):
        self.guild, self.text, self.vc, self.host = guild, text, vc, host
        self.players, self.phase, self.night_no = {}, "setup", 0
        self.act, self.done, self.ev = {}, set(), asyncio.Event()
        self.rage = self.rage_next = self.crazy = self.crazy_next = False
        self.fresh, self.sync_wolves = [], []
        self.result, self.stopped, self.voting = None, False, False
        self.votes, self.hang_immune = {}, set()
        self.victims, self.extra, self.biters, self.guard_t = [], {}, [], None
        self.morning, self.revived = [], []
        self.void_vc = self.void_text = self.wolf_ch = None
        self.alias, self.orig_nick = {}, {}
        self.tts, self.vclient, self.tts_q, self.tts_task = False, None, None, None
        self.role_ch, self.love_ch, self.sync_roles, self.new_lovers = {}, None, [], None
        roles = build_roles(len(members))
        random.shuffle(roles)
        for m, r in zip(members, roles):
            self.players[m.id] = P(m, r)

    # ---------- tiện ích ----------
    def alive(self): return [p for p in self.players.values() if p.alive]
    def nm(self, uid): return self.players[uid].name
    def rn(self, p): return f"{ROLES[p.role][1]} {ROLES[p.role][0]}"
    def over(self): return self.stopped or self.result is not None

    async def safe(self, coro):
        try:
            return await coro
        except discord.HTTPException:
            pass

    async def wait(self, secs):
        try:
            await asyncio.wait_for(self.ev.wait(), secs)
        except asyncio.TimeoutError:
            pass

    def known_wolf(self, q):
        return q.team == W and not (q.role == "kephanboi" and not q.s["awake"])

    def can_bite(self, p):
        return (p.alive and p.team == W and not (p.role == "kephanboi" and not p.s["awake"])
                and not (p.role == "soitientri" and not p.s["bite"]))

    def see_wolf(self, q):  # Tiên Tri nhìn thấy
        if q.role == "bansoi": return True
        if q.role == "kephanboi" and not q.s["awake"]: return False
        return q.team == W

    # ---------- kênh / voice ----------
    async def setup(self):
        dr, me = self.guild.default_role, self.guild.me
        mep = discord.PermissionOverwrite(view_channel=True, connect=True, speak=True, send_messages=True,
                                          manage_channels=True, mute_members=True, move_members=True)
        hid = discord.PermissionOverwrite(view_channel=False)
        cat = self.vc.category
        ow = {dr: hid, me: mep}
        self.void_vc = await self.guild.create_voice_channel("💀・Void-Âm-Phủ", category=cat, overwrites=ow)
        self.void_text = await self.guild.create_text_channel("âm-phủ", category=cat, overwrites=ow)
        self.wolf_ch = await self.guild.create_text_channel("hang-ma-sói", category=cat, overwrites=ow)
        await self.make_role_channels(mep, hid)
        await self.safe(self.void_text.send(
            "👻 **Âm Giới** — tin nhắn không hiện tên hay bí danh của ai (kể cả Thầy Đồng).\n"
            "Không gõ trực tiếp được. Dùng lệnh `/maso chat` hoặc bấm nút **Chat Âm Giới** bên dưới.",
            view=OpenView(self)))
        tc = self.role_ch.get("thaydong")
        if tc:
            await self.safe(tc.send("🪄 Ban đêm, **gõ thẳng vào phòng này** để chat Âm Giới ẩn danh. "
                                    "Tin của người chết cũng hiện ở đây. Tin của bạn sẽ được bot đăng lại ẩn danh hoàn toàn."))
        nums = random.sample(range(10, 100), len(self.players))
        for p, n in zip(self.players.values(), nums):
            p.name = f"Người bí ẩn #{n}"
        for p in self.players.values():
            await self.set_nick(p, p.name)
        # giao việc
        ps = list(self.players.values())
        for p in ps:
            if p.role == "daophu":
                cands = [q for q in ps if q.id != p.id and q.team == V] or [q for q in ps if q.id != p.id]
                p.s["target"] = random.choice(cands).id
                p.inbox.append(f"🪓 Mục tiêu của bạn: **{self.nm(p.s['target'])}**. Hãy khiến dân làng treo cổ họ!")
        for p in ps:
            if self.known_wolf(p):
                await self.add_wolf(p)
        await self.text.send(embed=discord.Embed(
            title="🎴 Vai trò đã được chia!",
            description=(f"**{len(ps)}** người chơi. Mọi người đã được đổi thành **🎭 Người bí ẩn #số** — hãy gọi nhau bằng số!\n"
                         "Bấm nút bên dưới để xem vai trò của bạn.\n"
                         f"Người chết sẽ bị chuyển sang {self.void_vc.mention}.\n"
                         "⚠️ Ai không ở kênh thoại sẽ không bị mute — hãy vào kênh thoại!"),
            color=0xF1C40F), view=OpenView(self))
        if VOICE_MASK == "tts":
            try:
                import edge_tts  # noqa: F401
                await self.safe(self.vc.set_permissions(self.guild.me, speak=True, connect=True))
                self.vclient = await self.vc.connect()
                self.tts, self.tts_q = True, asyncio.Queue()
                self.tts_task = asyncio.create_task(self.tts_worker())
                await self.text.send("🎙️ **Chế độ ẩn giọng**: mic của mọi người bị khóa cả ngày lẫn đêm. "
                                     "Ban ngày hãy **gõ chữ vào kênh này**, bot sẽ đọc to bằng một giọng chung.")
            except Exception as e:
                await self.text.send(f"⚠️ Không bật được giọng bot đọc ({e}). Ban ngày mic sẽ mở bình thường.")
        asyncio.create_task(self.enforce())
        await asyncio.sleep(10)

    def priv_ow(self, members):
        dr, me = self.guild.default_role, self.guild.me
        mep = discord.PermissionOverwrite(view_channel=True, connect=True, speak=True, send_messages=True,
                                          manage_channels=True, mute_members=True, move_members=True)
        ow = {dr: discord.PermissionOverwrite(view_channel=False), me: mep}
        for m in members:
            ow[m] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)
        return ow

    def tts_enqueue(self, p, text):
        text = " ".join(text.split())[:200]
        if text and self.tts_q and self.tts_q.qsize() < 15:
            self.tts_q.put_nowait(f"{p.name.replace('Người bí ẩn #', 'Số ')} nói: {text}".replace("🎭 ", ""))

    async def make_role_channels(self, mep=None, hid=None):
        """Mỗi chức năng 1 phòng chat riêng, chỉ người giữ vai đó vào được."""
        by = defaultdict(list)
        for p in self.players.values():
            if p.role not in ("danlang", "masoi"):
                by[p.role].append(p.m)
        for role, members in by.items():
            name, emo, team, desc = ROLES[role]
            cname = f"{emo}・{name}".lower().replace(" ", "-")
            try:
                ch = await self.guild.create_text_channel(cname, category=self.vc.category, overwrites=self.priv_ow(members))
            except discord.HTTPException:
                continue
            self.role_ch[role] = ch
            await self.safe(ch.send(
                f"{' '.join(m.mention for m in members)}\n**{emo} {name}** — {desc}\n"
                "Đây là phòng riêng của chức năng này, chỉ người giữ vai mới thấy."))

    async def move_role_ch(self, p, old):
        ch = self.role_ch.get(old)
        if ch: await self.safe(ch.set_permissions(p.m, overwrite=None))
        ch = self.role_ch.get(p.role)
        if ch and p.alive:
            await self.safe(ch.set_permissions(p.m, view_channel=True, send_messages=True, read_message_history=True))
            await self.safe(ch.send(f"**{p.name}** đã nhận vai **{self.rn(p)}**."))

    async def make_love_ch(self):
        """Phòng Vợ Chồng — chỉ 2 người được kết đôi vào; KHÔNG tiết lộ ai là Thần Tình Yêu."""
        if not self.new_lovers: return
        x, y = self.new_lovers
        self.new_lovers = None
        ms = {self.players[x].m, self.players[y].m}
        try:
            self.love_ch = await self.guild.create_text_channel("💘・vợ-chồng", category=self.vc.category,
                                                                overwrites=self.priv_ow(ms))
        except discord.HTTPException:
            return
        await self.safe(self.love_ch.send(
            f"{self.players[x].m.mention} 💘 {self.players[y].m.mention}\n"
            "Hai bạn đã được kết đôi! Một người chết thì người kia chết theo.\n"
            "🤫 Không ai (kể cả hai bạn) biết ai là Thần Tình Yêu."))

    def wolf_info(self, p):
        mates = [self.nm(q.id) for q in self.players.values() if q.id != p.id and self.known_wolf(q) and q.team == W]
        p.inbox.append("🐺 Đồng đội Sói: " + (", ".join(mates) if mates else "không có (bạn đơn độc)"))

    async def add_wolf(self, p):
        self.wolf_info(p)
        await self.safe(self.wolf_ch.set_permissions(p.m, view_channel=True, send_messages=True))

    async def mute_alive(self, mute):
        async def one(p):
            if mute and not (self.tts or self.phase in ("night", "late")): return
            m = self.guild.get_member(p.id) or p.m
            if m.voice and m.voice.channel and m.voice.mute != mute:
                await self.safe(m.edit(mute=mute))
        await asyncio.gather(*(one(p) for p in self.alive()))

    async def lock_voice(self, lock):
        """Đêm: cấm quyền nói ở kênh làng (vào lại cũng không nói được). Sáng: trả lại."""
        await self.safe(self.vc.set_permissions(self.guild.default_role, speak=False if lock else None))

    def can_void_chat(self, p):
        return (not p.alive) or (p.role == "thaydong" and self.phase in ("night", "late"))

    async def void_say(self, uid, text):
        """Đăng tin Âm Giới dưới bí danh ngẫu nhiên; chuyển tiếp sang phòng riêng của Thầy Đồng."""
        line = f"👻 **Linh hồn ẩn danh:** {text[:300]}"
        na = discord.AllowedMentions.none()
        await self.safe(self.void_text.send(line, allowed_mentions=na))
        tc = self.role_ch.get("thaydong")
        if tc and self.phase in ("night", "late") and any(q.role == "thaydong" for q in self.alive()):
            await self.safe(tc.send(line, allowed_mentions=na))

    async def enforce(self):
        """Canh mic: đêm (hoặc cả ngày nếu bật TTS) ai được mở mic / vừa vào kênh thì mute lại."""
        while self.phase != "end" and not self.stopped:
            await asyncio.sleep(3)
            if self.tts or self.phase in ("night", "late"):
                await self.mute_alive(True)

    async def tts_worker(self):
        """Đọc tin nhắn của người chơi bằng MỘT giọng máy chung -> không lộ giọng thật."""
        import edge_tts
        loop = asyncio.get_running_loop()
        while True:
            text = await self.tts_q.get()
            path = None
            try:
                if not (self.vclient and self.vclient.is_connected()): continue
                fd, path = tempfile.mkstemp(suffix=".mp3"); os.close(fd)
                await edge_tts.Communicate(text, TTS_VOICE).save(path)
                done = asyncio.Event()
                self.vclient.play(discord.FFmpegPCMAudio(path), after=lambda e: loop.call_soon_threadsafe(done.set))
                await done.wait()
            except Exception:
                traceback.print_exc()
            finally:
                if path and os.path.exists(path): os.remove(path)

    def can_void_chat(self, p):
        return (not p.alive) or (p.role == "thaydong" and self.phase in ("night", "late"))

    async def void_say(self, uid, text):
        """Đăng tin Âm Giới dưới bí danh ngẫu nhiên; chuyển tiếp sang phòng riêng của Thầy Đồng."""
        line = f"👻 **Linh hồn ẩn danh:** {text[:300]}"
        na = discord.AllowedMentions.none()
        await self.safe(self.void_text.send(line, allowed_mentions=na))
        tc = self.role_ch.get("thaydong")
        if tc and self.phase in ("night", "late") and any(q.role == "thaydong" for q in self.alive()):
            await self.safe(tc.send(line, allowed_mentions=na))

    async def enforce(self):
        """Suốt đêm cứ vài giây kiểm tra lại, ai lỡ được mở mic / vừa vào kênh thì mute lại ngay."""
        while self.phase in ("night", "late") and not self.stopped:
            await asyncio.sleep(3)
            if self.phase in ("night", "late"):
                await self.mute_alive(True)

    async def set_nick(self, p, nick):
        """Đổi nickname (lưu nickname gốc ở lần đổi đầu tiên)."""
        m = self.guild.get_member(p.id) or p.m
        if p.id not in self.orig_nick:
            self.orig_nick[p.id] = m.nick
        await self.safe(m.edit(nick=nick))

    async def restore_original(self, p):
        if p.id in self.orig_nick:
            m = self.guild.get_member(p.id) or p.m
            await self.safe(m.edit(nick=self.orig_nick.pop(p.id)))

    def expected_nick(self, p):
        return p.name if p.alive else ANON_NICK

    async def to_void(self, p):
        m = self.guild.get_member(p.id) or p.m
        await self.set_nick(p, ANON_NICK)
        await self.safe(self.void_vc.set_permissions(m, view_channel=True, connect=True, speak=True))
        await self.safe(self.void_text.set_permissions(m, view_channel=True, send_messages=False, read_message_history=True))
        await self.safe(self.text.set_permissions(m, send_messages=False))
        await self.safe(self.wolf_ch.set_permissions(m, send_messages=False))
        rc = self.role_ch.get(p.role)
        if rc: await self.safe(rc.set_permissions(m, send_messages=False))
        if self.love_ch and p.lover: await self.safe(self.love_ch.set_permissions(m, send_messages=False))
        if m.voice and m.voice.channel:
            await self.safe(m.edit(mute=False, voice_channel=self.void_vc))
        await self.safe(self.vc.set_permissions(m, connect=False))

    async def from_void(self, p):
        m = self.guild.get_member(p.id) or p.m
        await self.set_nick(p, p.name)
        for ch in (self.void_vc, self.void_text, self.vc, self.text):
            await self.safe(ch.set_permissions(m, overwrite=None))
        if self.known_wolf(p):
            await self.safe(self.wolf_ch.set_permissions(m, view_channel=True, send_messages=True))
        rc = self.role_ch.get(p.role)
        if rc: await self.safe(rc.set_permissions(m, view_channel=True, send_messages=True))
        if self.love_ch and p.lover: await self.safe(self.love_ch.set_permissions(m, send_messages=True))
        if m.voice and m.voice.channel:
            await self.safe(m.edit(mute=self.phase in ("night", "late"), voice_channel=self.vc))

    async def cleanup(self):
        self.phase = "end"
        if self.tts_task: self.tts_task.cancel()
        if self.vclient:
            try: await self.vclient.disconnect(force=True)
            except Exception: pass
        self.tts = False
        await self.lock_voice(False)
        for p in self.players.values():
            await self.restore_original(p)  # hết trận mới trả lại tên thật
        for p in self.players.values():
            m = self.guild.get_member(p.id) or p.m
            if m.voice and m.voice.channel:
                await self.safe(m.edit(mute=False, voice_channel=self.vc))
            for ch in (self.vc, self.text):
                await self.safe(ch.set_permissions(m, overwrite=None))
        for ch in [self.void_vc, self.void_text, self.wolf_ch, self.love_ch, *self.role_ch.values()]:
            if ch: await self.safe(ch.delete())

    # ---------- vòng lặp ----------
    async def run(self):
        try:
            await self.setup()
            while not self.over():
                await self.night()
                if self.over(): break
                await self.day()
            await self.finish()
        except Exception as e:
            traceback.print_exc()
            await self.safe(self.text.send(f"⚠️ Lỗi: `{e}` — ván bị hủy."))
            await self.cleanup()
        finally:
            GAMES.pop(self.guild.id, None)

    async def finish(self):
        self.phase = "end"
        e = discord.Embed(color=0xF1C40F)
        if self.stopped:
            e.title = "🛑 Ván đấu đã bị dừng"
        else:
            title, wins = self.result
            e.title = f"🏆 {title}"
            e.description = "Người thắng: " + (", ".join(f"**{self.players[u].real}** ({self.players[u].name})" for u in wins) or "không ai")
        e.add_field(name="Vai trò", inline=False, value="\n".join(
            f"{'🟢' if p.alive else '💀'} **{p.real}** ({p.name}) — {self.rn(p)}" for p in self.players.values())[:1000])
        await self.text.send(embed=e)
        await self.cleanup()

    # ---------- đêm ----------
    def need(self):
        return {p.id for p in self.alive() if self.skills(p)}

    def mark(self, uid):
        self.done.add(uid)
        if self.need() <= self.done:
            self.ev.set()

    async def night(self):
        self.phase, self.night_no = "night", self.night_no + 1
        self.act, self.done, self.ev = {}, set(), asyncio.Event()
        self.rage, self.rage_next = self.rage_next, False
        self.crazy, self.crazy_next = self.crazy_next, False
        for p in self.players.values():
            p.dis, p.nm_next = p.nm_next, False
            if p.alive and p.convert_next:
                p.convert_next = False
                old = p.role
                p.set_role("masoi")
                await self.move_role_ch(p, old)
                p.inbox.append("🐺 Bạn đã biến thành **Ma Sói**!")
                await self.add_wolf(p)
        await self.check_traitor()
        for p in self.alive():
            if p.role == "soitientri" and not any(self.can_bite(q) for q in self.alive()):
                p.s["bite"] = 1
                p.inbox.append("🐺 Bạn là Sói duy nhất nên tự hóa Sói thường.")
        await self.lock_voice(True)
        await self.mute_alive(True)
        extra = "\n🌋 **Thịnh nộ!** Bầy Sói được cắn 2 người đêm nay." if self.rage else ""
        await self.text.send(embed=discord.Embed(
            title=f"🌙 Đêm thứ {self.night_no}",
            description=("Làng chìm vào giấc ngủ. **Mic của mọi người sống đã bị tắt** cho tới sáng.\n"
                         "Người có chức năng bấm nút bên dưới để hành động. Sói chat ở "
                         f"{self.wolf_ch.mention}." + extra), color=0x2C3E50), view=OpenView(self))
        t0 = time.time()
        if not self.need(): self.ev.set()
        await self.wait(NIGHT_SECS)
        await asyncio.sleep(max(0, MIN_SECS - (time.time() - t0)))
        if self.stopped: return
        self.prep_night()
        await self.make_love_ch()
        # giai đoạn đêm sắp kết thúc
        self.phase, self.done, self.ev = "late", set(), asyncio.Event()
        if self.need():
            await self.text.send(embed=discord.Embed(
                title="🌒 Đêm sắp kết thúc...",
                description="⚗️ Phù Thủy / 🪄 Thầy Đồng: bấm nút để dùng bình thuốc hoặc hồi sinh.", color=0x34495E),
                view=OpenView(self))
            await self.wait(LATE_SECS)
        if self.stopped: return
        self.finish_night()
        dead = await self.flush()
        for p in self.alive():  # Thầy Đồng hồi sinh
            pool = [x for x in self.players.values() if not x.alive]
            if p.role == "thaydong" and self.act.get(p.id, {}).get("revive") and p.s["rev"] and pool:
                q = random.choice(pool)
                if not q.alive:
                    p.s["rev"] = 0
                    q.alive = True
                    q.inbox.append("🪄 Bạn đã được hồi sinh!")
                    await self.from_void(q)
                    self.revived.append(q)
                    if q in dead: dead.remove(q)
        self.morning = dead
        await self.check_traitor()
        self.check_set()

    def ok_targets(self, p, key):
        al = self.alive()
        ids = {q.id for q in al}
        others = ids - {p.id}
        if key == "bite":
            return {q.id for q in al if q.id != p.id and not self.known_wolf(q)}
        if key == "guard": return ids - {p.s["last"]}
        if key in ("cupid", "detective", "psychic", "protect", "gprot"): return ids
        if key == "cat": return {q.id for q in al if q.id != p.id and q.team == V}
        if key == "revive": return {q.id for q in self.players.values() if not q.alive}
        if key == "cult": return {q.id for q in al if q.id != p.id and not q.cult}
        return others

    def skills(self, p):
        """Danh sách kỹ năng khả dụng: (loại, key, nhãn, min, max)"""
        if not p.alive: return []
        ph, r, s, o = self.phase, p.role, p.s, []
        if ph == "night":
            if p.dis: return []
            n1 = self.night_no == 1
            if self.can_bite(p):
                o.append(("sel", "bite", "🐺 Chọn mục tiêu cắn" + (" (tối đa 2)" if self.rage else ""), 1, 2 if self.rage else 1))
            if r == "tientri": o.append(("sel", "seer", "🔮 Soi 1 người", 1, 1))
            if r == "baove": o.append(("sel", "guard", "🛡️ Bảo vệ 1 người", 1, 1))
            if r == "tinhyeu" and n1: o.append(("sel", "cupid", "💘 Chọn 2 người kết đôi", 2, 2))
            if r == "thosan" and not s["shot"]: o.append(("sel", "hunter", "🏹 Nổ súng (tùy chọn)", 1, 1))
            if r == "musu": o.append(("sel", "priest", "✝️ Vẩy nước thánh", 1, 1))
            if r == "thamtu": o.append(("sel", "detective", "🕵️ Chọn 2 người so sánh phe", 2, 2))
            if r == "ngoaicam": o.append(("sel", "psychic", "🔭 Chọn 2 người", 2, 2))
            if r == "kebatchuoc" and n1: o.append(("sel", "copy", "🎭 Chọn người đối bóng", 1, 1))
            if r == "satnhan": o.append(("sel", "sk", "🔪 Giết 1 người", 1, 1))
            if r == "anthit":
                o.append(("sel", "eat", f"🍖 Nuốt tối đa {min(5, 1 + s['hunger'])} người", 1, min(5, 1 + s["hunger"])))
                o.append(("btn", "starve", "🍽️ Nhịn đói (tích điểm)", 0, 0))
            if r == "giaochu": o.append(("sel", "cult", "🌀 Thu phục 1 người", 1, 1))
            if r == "soitientri":
                o.append(("sel", "wseer", "🔮 Soi vai trò (chia sẻ bầy)", 1, 1))
                if not s["bite"]: o.append(("btn", "unwolf", "🐺 Hóa Sói Thường", 0, 0))
            if r == "soitre" and n1: o.append(("sel", "link", "💞 Gắn bó sinh tử", 1, 1))
            if r == "soimeocon" and not s["used"]: o.append(("sel", "cat", "🐱 Biến 1 người thành Sói", 1, 1))
            if r == "soiphantach" and not s["bound"]: o.append(("sel", "split", "⛓️ Ràng buộc 1 người", 1, 1))
            if r == "thoren":
                if s["pending"]:
                    o.append(("sel", "give", f"🔨 Trao {'Khiên' if s['pending'] == 'shield' else 'Kiếm'} cho ai?", 1, 1))
                else:
                    if s["fs"] < 2: o.append(("btn", "forge_shield", "🛡️ Rèn Khiên", 0, 0))
                    if s["fw"] < 1: o.append(("btn", "forge_sword", "🗡️ Rèn Kiếm", 0, 0))
            if p.sword: o.append(("sel", "sword", "⚔️ Dùng Kiếm giết 1 người", 1, 1))
            if o: o.append(("btn", "skip", "😴 Xong / Ngủ", 0, 0))
        elif ph == "late":
            if p.dis: return []
            if r == "phuthuy":
                if s["heal"]:
                    for v in self.victims:
                        o.append(("btn", f"heal:{v}", f"💊 Cứu {self.nm(v)[:20]}", 0, 0))
                if s["poison"]: o.append(("sel", "poison", "☠️ Bình Độc: giết 1 người", 1, 1))
            if r == "thaydong" and s["rev"] and any(not q.alive for q in self.players.values()):
                o.append(("btn", "revive", "🎲 Hồi sinh ngẫu nhiên 1 linh hồn", 0, 0))
            if o: o.append(("btn", "skip", "😴 Xong", 0, 0))
        elif ph == "day":
            if r == "hoabenho" and not s["used"]: o.append(("sel", "protect", "🌸 Miễn nhiễm treo cổ cho 1 người", 1, 1))
            if r == "soiacmong" and s["left"] > 0: o.append(("sel", "nm", f"😱 Ru ác mộng (còn {s['left']})", 1, 1))
            if r == "soidiencuong" and not s["used"]: o.append(("btn", "crazy", "🔥 Kích hoạt Điên Cuồng", 0, 0))
            if r == "soibaoho" and not s["used"]: o.append(("sel", "gprot", "🛡️ Miễn nhiễm treo cổ cho 1 người", 1, 1))
            if r == "soiphaohoa" and s["fw"] > 0: o.append(("sel", "fw", f"🎆 Đốt pháo hoa (tối đa {s['fw']})", 1, s["fw"]))
        return o

    # ---------- menu ----------
    async def open_menu(self, i):
        p = self.players.get(i.user.id)
        if not p:
            return await i.response.send_message("Bạn không tham gia ván này.", ephemeral=True)
        name, emo, team, desc = ROLES[p.role]
        e = discord.Embed(title=f"{emo} {name}", description=desc, color=COLOR[p.team])
        e.add_field(name="Phe", value=PHE[p.team])
        st = []
        if not p.alive: st.append("💀 Bạn đã chết")
        if p.lover: st.append(f"💘 Cặp đôi: {self.nm(p.lover)}")
        if p.cult: st.append("🌀 Thuộc Giáo Phái")
        if p.shield: st.append(f"🛡️ Khiên x{p.shield}")
        if p.sword: st.append("🗡️ Đang giữ Kiếm")
        if p.dis and self.phase in ("night", "late"): st.append("😱 Bạn đang bị Ác Mộng — không dùng được kỹ năng đêm nay")
        if p.role == "soiphaohoa": st.append(f"🎆 Pháo hoa: {p.s['fw']}")
        if p.role == "anthit": st.append(f"🍽️ Điểm đói: {p.s['hunger']}")
        if st: e.add_field(name="Trạng thái", value="\n".join(st), inline=False)
        if self.phase == "late" and p.role == "phuthuy" and p.s["heal"]:
            e.add_field(name="🩸 Nạn nhân bị Sói cắn", value=", ".join(self.nm(v) for v in self.victims) or "Không có", inline=False)
        if p.inbox:
            e.add_field(name="📨 Thông tin", value="\n".join(p.inbox[-8:])[:1000], inline=False)
        v = discord.ui.View(timeout=240)
        for sk in self.skills(p):
            v.add_item(SkillSelect(self, p, sk[1], sk[2], sk[3], sk[4]) if sk[0] == "sel"
                       else SkillButton(self, p, sk[1], sk[2]))
        await i.response.send_message(embed=e, view=v, ephemeral=True)

    async def open_chat(self, i):
        p = self.players.get(i.user.id)
        if not p or not (not p.alive or (p.role == "thaydong" and self.phase in ("night", "late"))):
            return await i.response.send_message("Chỉ người chết hoặc Thầy Đồng (ban đêm) dùng được.", ephemeral=True)
        await i.response.send_modal(ChatModal(self))

    # ---------- xử lý chọn kỹ năng ----------
    async def on_pick(self, i, p, key, ids):
        if not any(sk[1] == key for sk in self.skills(p)):
            return await i.response.send_message("Kỹ năng không còn khả dụng.", ephemeral=True)
        if len(set(ids)) != len(ids) or not set(ids) <= self.ok_targets(p, key):
            return await i.response.send_message("Mục tiêu không hợp lệ.", ephemeral=True)
        if key in ("cupid", "detective", "psychic") and len(ids) != 2:
            return await i.response.send_message("Phải chọn đúng 2 người.", ephemeral=True)
        A = self.act.setdefault(p.id, {})
        if key in LOCK and key in A:
            return await i.response.send_message("Bạn đã dùng kỹ năng này đêm nay rồi.", ephemeral=True)
        names = ", ".join(self.nm(x) for x in ids)
        msg = f"✅ Đã chọn: **{names}**"
        ph = self.phase
        if ph in ("night", "late"):
            A[key] = ids
            if key == "eat": A.pop("starve", None)
        if key == "seer":
            res = "Ma Sói 🐺" if self.see_wolf(self.players[ids[0]]) else "Dân Làng 🧑‍🌾"
            msg = f"🔮 **{names}** thuộc phe: **{res}**"
            p.inbox.append(f"Đêm {self.night_no}: {msg}")
        elif key == "detective":
            a, b = self.players[ids[0]], self.players[ids[1]]
            res = "CÙNG PHE ✅" if a.team == b.team else "KHÁC PHE ❌"
            msg = f"🕵️ **{names}**: {res}"
            p.inbox.append(f"Đêm {self.night_no}: {msg}")
        elif key == "wseer":
            q = self.players[ids[0]]
            msg = f"🔮 **{q.name}** là **{self.rn(q)}**"
            for w in self.players.values():
                if w.team == W and self.known_wolf(w):
                    w.inbox.append(f"Đêm {self.night_no} (Sói Tiên Tri): {msg}")
        elif key == "give":
            q = self.players[ids[0]]
            if p.s["pending"] == "shield":
                q.shield += 1
                q.inbox.append("🛡️ Thợ Rèn đã trao cho bạn 1 **Khiên** (chống 1 lần cắn).")
            else:
                q.sword = True
                q.inbox.append("🗡️ Thợ Rèn đã trao cho bạn 1 **Kiếm** — dùng ban đêm để giết 1 người.")
            p.s["pending"] = 0
            msg = f"🔨 Đã trao vật phẩm cho **{names}**"
        elif key in ("protect", "gprot"):
            p.s["used"] = 1
            self.hang_immune.add(ids[0])
            msg = f"🌸 **{names}** sẽ miễn nhiễm treo cổ hôm nay."
        elif key == "nm":
            p.s["left"] -= 1
            self.players[ids[0]].nm_next = True
            msg = f"😱 **{names}** sẽ gặp Ác Mộng đêm sau."
        elif key == "fw":
            ids = ids[:p.s["fw"]]
            p.s["fw"] -= len(ids)
            await i.response.send_message(f"🎆 Bạn đốt {len(ids)} pháo hoa!", ephemeral=True)
            await self.text.send(f"🎆 **Sói Pháo Hoa {p.name} lộ diện** và đốt pháo hoa!")
            for t in ids: self.kill(t, "fw")
            dead = await self.flush()
            await self.announce(dead, "🎆 Pháo hoa nổ tung! Đã chết", reveal=False)
            await self.check_traitor()
            self.check_set()
            return
        if ph in ("night", "late"): self.mark(p.id)
        await i.response.send_message(msg, ephemeral=True)

    async def on_button(self, i, p, key):
        if not any(sk[1] == key for sk in self.skills(p)):
            return await i.response.send_message("Kỹ năng không còn khả dụng.", ephemeral=True)
        A = self.act.setdefault(p.id, {})
        msg = "✅ Đã ghi nhận."
        if key == "skip": msg = "😴 Bạn đã đi ngủ."
        elif key == "starve": A["starve"] = 1; A.pop("eat", None); msg = "🍽️ Bạn nhịn đói để ăn bù đêm sau."
        elif key in ("forge_shield", "forge_sword"): A[key] = 1; msg = "🔨 Bạn bắt đầu rèn..."
        elif key == "unwolf":
            p.s["bite"] = 1
            msg = "🐺 Bạn đã hóa Sói thường và có thể cắn."
        elif key == "crazy":
            p.s["used"] = 1
            self.crazy_next = True
            msg = "🔥 Bầy Sói sẽ Điên Cuồng đêm sau!"
        elif key == "revive": A["revive"] = 1; msg = "🎲 Một linh hồn ngẫu nhiên (có thể cả Sói) sẽ trở lại khi đêm kết thúc."
        elif key.startswith("heal:"):
            A["heal"] = int(key[5:]); msg = "💊 Bạn dùng Bình Cứu."
        if self.phase in ("night", "late"): self.mark(p.id)
        await i.response.send_message(msg, ephemeral=True)

    # ---------- tính toán đêm ----------
    def prep_night(self):
        A, al = self.act, self.alive()
        get = lambda p, k: A.get(p.id, {}).get(k)
        self.guard_t = None
        for p in al:
            if p.role == "baove":
                t = get(p, "guard")
                p.s["last"] = t[0] if t else 0
                if t: self.guard_t = (p.id, t[0])
        for p in al:
            a = A.get(p.id, {})
            if "cupid" in a and self.night_no == 1:
                x, y = a["cupid"]
                self.players[x].lover, self.players[y].lover = y, x
                self.new_lovers = (x, y)
                self.players[x].inbox.append(f"💘 Bạn kết đôi với **{self.nm(y)}** (xem phòng 💘・vợ-chồng). Không ai biết Thần Tình Yêu là ai.")
                self.players[y].inbox.append(f"💘 Bạn kết đôi với **{self.nm(x)}** (xem phòng 💘・vợ-chồng). Không ai biết Thần Tình Yêu là ai.")
            if "copy" in a:
                p.s["copy"] = a["copy"][0]
                p.inbox.append(f"🎭 Bạn đối bóng với **{self.nm(a['copy'][0])}**.")
            if "link" in a:
                p.s["link"] = a["link"][0]
                p.inbox.append(f"💞 Bạn gắn bó sinh tử với **{self.nm(a['link'][0])}**.")
            if "split" in a:
                p.s["bound"] = a["split"][0]
                p.inbox.append(f"⛓️ Bạn ràng buộc **{self.nm(a['split'][0])}** (tính là 2 Sói).")
            if "cat" in a:
                p.s["used"] = 1
                t = self.players[a["cat"][0]]
                ok = t.alive and t.team == V and not (self.guard_t and self.guard_t[1] == t.id)
                if ok:
                    t.convert_next = True
                    t.inbox.append("🐱 Bạn bị Sói Mèo Con cắn — đêm sau bạn sẽ thành Ma Sói!")
                for w in self.players.values():
                    if w.team == W and self.known_wolf(w):
                        w.inbox.append(f"🐱 Sói Mèo Con biến **{t.name}**: {'THÀNH CÔNG' if ok else 'thất bại'}.")
            if "cult" in a:
                t = self.players[a["cult"][0]]
                t.cult = True
                t.inbox.append("🌀 Bạn đã bị Giáo Chủ thu phục vào Giáo Phái!")
                p.inbox.append(f"🌀 Đã thu phục **{t.name}**.")
            if "forge_shield" in a: p.s["pending"] = "shield"; p.s["fs"] += 1; p.inbox.append("🛡️ Bạn đã rèn xong 1 Khiên — hãy trao cho ai đó.")
            if "forge_sword" in a: p.s["pending"] = "sword"; p.s["fw"] += 1; p.inbox.append("🗡️ Bạn đã rèn xong 1 Kiếm — hãy trao cho ai đó.")
        # Sói cắn
        tally, self.biters = defaultdict(int), []
        for p in al:
            t = get(p, "bite")
            if t and self.can_bite(p):
                self.biters.append(p.id)
                for x in t: tally[x] += 2 if p.role == "doaudan" else 1
        top = sorted(tally.items(), key=lambda kv: (-kv[1], random.random()))
        targets = [t for t, _ in top[:2 if self.rage else 1]]
        self.victims, self.extra = [], {}
        for t in targets:
            q = self.players[t]
            if not q.alive or q.role == "anthit": continue
            guarded = bool(self.guard_t and self.guard_t[1] == t)
            if guarded and not self.crazy: continue
            if not guarded and q.shield and not self.crazy:
                q.shield -= 1
                q.inbox.append("🛡️ Khiên của bạn đã vỡ khi chặn Ma Sói!")
                continue
            if q.role == "gialang" and q.s["lives"] > 1:
                q.s["lives"] -= 1
                q.inbox.append("👴 Bạn bị Sói cắn nhưng còn mạng thứ 2 — đã mất 1 mạng.")
                continue
            if q.role == "bansoi":
                q.convert_next = True
                q.inbox.append("🌗 Bạn bị Sói cắn — đêm sau bạn sẽ thành Ma Sói!")
                continue
            self.victims.append(t)
            if guarded and self.crazy: self.extra[t] = self.guard_t[0]

    def finish_night(self):
        A, al = self.act, self.alive()
        healed, doers = set(), set(self.biters)
        for p in al:
            a = A.get(p.id, {})
            r = p.role
            if r == "phuthuy":
                if "heal" in a and p.s["heal"]: p.s["heal"] = 0; healed.add(a["heal"])
                if "poison" in a and p.s["poison"]:
                    p.s["poison"] = 0; self.kill(a["poison"][0], "poison"); doers.add(p.id)
            if r == "satnhan" and "sk" in a: self.kill(a["sk"][0], "sk"); doers.add(p.id)
            if r == "anthit":
                if "eat" in a:
                    for t in a["eat"]: self.kill(t, "eat")
                    p.s["hunger"] = 0; doers.add(p.id)
                elif "starve" in a: p.s["hunger"] = min(4, p.s["hunger"] + 1)
            if r == "thosan" and "hunter" in a and not p.s["shot"]:
                p.s["shot"] = 1; self.kill(a["hunter"][0], "hunter"); doers.add(p.id)
            if "sword" in a and p.sword:
                p.sword = False; self.kill(a["sword"][0], "sword"); doers.add(p.id)
            if r == "musu" and "priest" in a:
                t = self.players[a["priest"][0]]
                self.kill(t.id if t.team == W else p.id, "priest"); doers.add(p.id)
        bite_deaths = 0
        for v in self.victims:
            if v in healed:
                self.players[v].inbox.append("💊 Bạn bị Sói cắn nhưng đã được Phù Thủy cứu!")
                continue
            if self.players[v].alive: bite_deaths += 1
            self.kill(v, "wolf")
            if v in self.extra: self.kill(self.extra[v], "crazy")
        for p in al:  # Ngoại Cảm
            a = A.get(p.id, {})
            if p.role == "ngoaicam" and "psychic" in a:
                x, y = a["psychic"]
                res = "CÓ" if (x in doers or y in doers) else "KHÔNG"
                p.inbox.append(f"🔭 Đêm {self.night_no}: trong **{self.nm(x)}** & **{self.nm(y)}** — {res} ai đã giết người.")
            if p.role == "soiphaohoa" and bite_deaths == 0 and p.alive:
                p.s["fw"] = min(2, p.s["fw"] + 1)
                p.inbox.append(f"🎆 Đêm bình yên: bạn có {p.s['fw']} pháo hoa.")

    # ---------- cái chết ----------
    def kill(self, uid, cause=""):
        p = self.players.get(uid)
        if not p or not p.alive: return
        p.alive = False
        self.fresh.append(p)
        if p.role == "soicon": self.rage_next = True
        if p.role == "giaochu":
            for q in self.alive():
                if q.cult: self.kill(q.id, "cult")
        if p.lover: self.kill(p.lover, "love")
        if p.role == "soiphantach" and p.s["bound"]: self.kill(p.s["bound"], "split")
        if p.role == "soitre" and p.s["link"]: self.kill(p.s["link"], "link")
        for q in self.alive():
            if q.role == "soiphantach" and q.s["bound"] == p.id:
                q.exposed = True
                self.fresh_reveal = getattr(self, "fresh_reveal", []) + [q]
            if q.role == "kebatchuoc" and q.s["copy"] == p.id:
                self.sync_roles.append((q, q.role))
                q.set_role(p.role)
                q.inbox.append(f"🎭 Bạn đã nhận vai trò **{self.rn(p)}**!")
                if q.team == W: self.sync_wolves.append(q)
            if q.role == "daophu" and q.s["target"] == p.id and cause != "hang":
                self.sync_roles.append((q, q.role))
                q.set_role("danlang")
                q.inbox.append("🪓 Mục tiêu đã chết — bạn trở thành Dân Làng.")

    async def flush(self):
        out = []
        while self.fresh:
            p = self.fresh.pop(0)
            out.append(p)
            await self.to_void(p)
            if p.role == "thosan" and not p.s["shot"]:
                p.s["shot"] = 1
                t = await self.ask_hunter(p)
                if t: self.kill(t, "hunter")
        for q in self.sync_wolves: await self.add_wolf(q)
        self.sync_wolves.clear()
        for q, old in self.sync_roles: await self.move_role_ch(q, old)
        self.sync_roles.clear()
        for q in getattr(self, "fresh_reveal", []):
            await self.text.send(f"⛓️ Vai trò của **{q.name}** bị lộ: **{self.rn(q)}**!")
        self.fresh_reveal = []
        return out

    async def ask_hunter(self, p):
        fut = asyncio.get_event_loop().create_future()
        view = discord.ui.View(timeout=30)
        sel = discord.ui.UserSelect(placeholder="🏹 Chọn người bắn hạ", min_values=1, max_values=1)

        async def cb(i):
            if i.user.id != p.id:
                return await i.response.send_message("Không phải lượt của bạn.", ephemeral=True)
            t = sel.values[0].id
            if t not in self.players or not self.players[t].alive:
                return await i.response.send_message("Mục tiêu không hợp lệ.", ephemeral=True)
            await i.response.send_message("🏹 Pằng!", ephemeral=True)
            if not fut.done(): fut.set_result(t)
        sel.callback = cb
        view.add_item(sel)
        msg = await self.text.send(f"🏹 {p.m.mention} — **{p.name}** (Thợ Săn) đã chết! Bạn có **30 giây** để bắn kéo theo 1 người.", view=view)
        try:
            t = await asyncio.wait_for(fut, 30)
        except asyncio.TimeoutError:
            t = None
        await self.safe(msg.edit(view=None))
        if t: await self.text.send(f"🏹 Thợ Săn đã bắn hạ **{self.nm(t)}**!")
        return t

    async def check_traitor(self):
        if not [p for p in self.alive() if p.team == W and p.role != "kephanboi"]:
            for p in self.alive():
                if p.role == "kephanboi" and not p.s["awake"]:
                    p.s["awake"] = 1
                    p.inbox.append("🗡️ Mọi Sói thật đã chết — bạn **thức tỉnh thành Ma Sói** và có thể cắn!")
                    await self.add_wolf(p)

    def check_win(self):
        al = self.alive()
        if not al: return ("Không ai sống sót", [])
        if len(al) == 1 and al[0].role in ("satnhan", "anthit"):
            return (f"{self.rn(al[0])} thắng!", [al[0].id])
        if any(p.role == "giaochu" for p in al) and all(p.cult or p.role == "giaochu" for p in al):
            return ("Giáo Phái thắng! 🌀", [p.id for p in self.players.values() if p.cult or p.role == "giaochu"])
        wolves = sum(2 if (p.role == "soiphantach" and p.s["bound"] and self.players[p.s["bound"]].alive) else 1
                     for p in al if p.team == W)
        vill = sum(1 for p in al if p.team == V)
        if wolves == 0:
            return ("Phe Dân Làng thắng! 🧑‍🌾", [p.id for p in self.players.values() if p.team == V])
        if wolves >= vill:
            return ("Phe Ma Sói thắng! 🐺", [p.id for p in self.players.values() if p.team == W])
        return None

    def check_set(self):
        r = self.check_win()
        if r:
            self.result = r
            self.ev.set()

    async def announce(self, dead, head, reveal=False):
        if not dead: return
        lines = []
        for p in dead:
            lines.append(f"💀 **{p.name}**" + (f" — {PHE[p.team]}" if reveal else ""))
        await self.text.send(embed=discord.Embed(title=head, description="\n".join(lines), color=0x992D22))

    # ---------- ngày ----------
    async def day(self):
        self.phase, self.hang_immune, self.voting = "day", set(), False
        self.ev = asyncio.Event()
        await self.lock_voice(self.tts)
        await self.mute_alive(self.tts)
        e = discord.Embed(title=f"☀️ Ngày thứ {self.night_no}", color=0xF1C40F)
        e.description = ("⌨️ Mic bị khóa — gõ chữ vào kênh này, bot đọc bằng giọng chung. Hãy thảo luận!" if self.tts
                         else "🔊 Mic đã được mở. Hãy thảo luận!")
        if self.morning:
            e.add_field(name="☠️ Đêm qua đã chết (không lộ vai trò)", value="\n".join(f"**{p.name}**" for p in self.morning), inline=False)
        else:
            e.add_field(name="🌅", value="Đêm qua bình yên, không ai chết.", inline=False)
        if self.revived:
            e.add_field(name="✨ Hồi sinh", value="\n".join(f"**{p.name}**" for p in self.revived), inline=False)
        e.add_field(name=f"Còn sống ({len(self.alive())})", value=", ".join(p.name for p in self.alive())[:1000], inline=False)
        self.morning, self.revived = [], []
        await self.text.send(embed=e, view=OpenView(self))
        await self.wait(DAY_SECS)
        if self.over(): return
        # biểu quyết
        al = self.alive()
        self.votes, self.voting, self.ev = {}, True, asyncio.Event()
        thr = max(1, len(al) // 2)
        await self.text.send(embed=discord.Embed(
            title="🗳️ Biểu quyết treo cổ",
            description=f"Ngưỡng vote = Floor({len(al)}/2) = **{thr}** phiếu. Trưởng Làng x2. Có {VOTE_SECS}s.", color=0xE67E22),
            view=VoteView(self))
        await self.wait(VOTE_SECS)
        self.voting = False
        if self.over(): return
        tally = defaultdict(int)
        for v, t in self.votes.items():
            if t: tally[t] += 2 if self.players[v].role == "truonglang" else 1
        lines = [f"**{self.nm(t)}**: {c} phiếu" for t, c in sorted(tally.items(), key=lambda kv: -kv[1])]
        await self.text.send("📊 Kết quả vote:\n" + ("\n".join(lines) or "Không ai bỏ phiếu."))
        if tally:
            top = max(tally.values())
            winners = [t for t, c in tally.items() if c == top]
            if len(winners) == 1 and top >= thr:
                t = winners[0]
                if t in self.hang_immune:
                    await self.text.send(f"🛡️ **{self.nm(t)}** được miễn nhiễm — không ai bị treo cổ!")
                else:
                    victim = self.players[t]
                    self.kill(t, "hang")
                    dead = await self.flush()
                    await self.announce(dead, "⚖️ Bị treo cổ — LỘ PHE", reveal=True)
                    if victim.role == "thangngo":
                        self.result = ("Thằng Ngố 🤡 thắng!", [victim.id]); return
                    for q in self.alive():
                        if q.role == "daophu" and q.s["target"] == t:
                            self.result = ("Đao Phủ 🪓 thắng!", [q.id]); return
                    await self.check_traitor()
                    self.check_set()
                    return
        await self.text.send("⚖️ Không ai bị treo cổ hôm nay.")

    async def cast(self, i, target):
        p = self.players.get(i.user.id)
        if not (self.voting and p and p.alive):
            return await i.response.send_message("Bạn không thể bỏ phiếu lúc này.", ephemeral=True)
        if target and (target not in self.players or not self.players[target].alive):
            return await i.response.send_message("Mục tiêu không hợp lệ.", ephemeral=True)
        self.votes[p.id] = target
        await i.response.send_message("✅ Đã bỏ phiếu: " + (f"**{self.nm(target)}**" if target else "bỏ qua"), ephemeral=True)
        if len(self.votes) >= len(self.alive()): self.ev.set()

    def stop(self):
        self.stopped = True
        self.ev.set()


# ============================ BOT ============================
intents = discord.Intents.default()
intents.members = True
intents.voice_states = True
intents.message_content = True  # cần bật 'Message Content Intent' trong Developer Portal


class MaSoi(commands.Bot):
    async def setup_hook(self):
        await self.tree.sync()


bot = MaSoi(command_prefix="!", intents=intents)
group = app_commands.Group(name="maso", description="Ma Sói")

GUIDE = """☀️ **1. Ban Ngày**
• **Thảo luận**: người sống trao đổi, tìm kẻ tình nghi (mic được mở).
• **Kỹ năng ban ngày**: Sói Bảo Hộ, Ác Mộng, Điên Cuồng, Pháo Hoa, Hoa Bé Nhỏ bấm nút *Xem vai trò / Dùng kỹ năng*.
• **Biểu quyết treo cổ**: chọn người nghi ngờ hoặc bấm *Bỏ qua*.
• **Ngưỡng vote** = Floor(Số người sống / 2). Người bị treo phải có phiếu cao nhất và ≥ ngưỡng.
• Khi bị treo cổ: **LỘ PHE** (Thiện / Ác / Trung Lập).

🌙 **2. Ban Đêm**
• **Mic của mọi người sống bị tắt** đến sáng. Dân làng ngủ say.
• Sói và các vai chức năng bấm nút để mở menu chọn mục tiêu.
• Chết trong đêm (Sói cắn, thuốc độc, thợ săn...) **KHÔNG LỘ VAI TRÒ**.
• Gần sáng: Phù Thủy / Thầy Đồng có thêm một lượt hành động.

🏆 **3. Điều kiện thắng**
• **Dân Làng**: tiêu diệt toàn bộ Ma Sói.
• **Ma Sói**: số Sói ≥ số Dân Làng còn sống.
• **Trung Lập**: hoàn thành mục tiêu riêng.

👻 **4. Âm Giới**
Người chết bị chuyển sang kênh thoại *Void Âm Phủ*, trò chuyện với các linh hồn khác."""


@group.command(name="batdau", description="Tạo phòng chờ Ma Sói (bạn phải đang ở kênh thoại)")
async def batdau(i: discord.Interaction):
    if i.guild.id in GAMES:
        return await i.response.send_message("Đang có ván diễn ra.", ephemeral=True)
    if not (i.user.voice and i.user.voice.channel):
        return await i.response.send_message("Hãy vào một kênh thoại trước (đó sẽ là kênh của làng).", ephemeral=True)
    lobby = Lobby(i.user, i.user.voice.channel)
    await i.response.send_message(embed=lobby.embed(), view=lobby)


@group.command(name="dung", description="Dừng ván đang chơi và mở lại mic")
async def dung(i: discord.Interaction):
    g = GAMES.get(i.guild.id)
    if not g: return await i.response.send_message("Không có ván nào.", ephemeral=True)
    if i.user.id != g.host.id and not i.user.guild_permissions.manage_guild:
        return await i.response.send_message("Chỉ chủ phòng hoặc quản trị viên.", ephemeral=True)
    g.stop()
    await i.response.send_message("🛑 Đang dừng ván...")


@group.command(name="momic", description="Khẩn cấp: bỏ mute mọi người trong kênh thoại của bạn")
@app_commands.checks.has_permissions(mute_members=True)
async def momic(i: discord.Interaction):
    if not (i.user.voice and i.user.voice.channel):
        return await i.response.send_message("Bạn chưa ở kênh thoại.", ephemeral=True)
    await i.response.defer(ephemeral=True)
    for m in i.user.voice.channel.members:
        try: await m.edit(mute=False)
        except discord.HTTPException: pass
    await i.followup.send("Đã mở mic.")


@group.command(name="chat", description="Chat ẩn danh ở Âm Giới (người chết / Thầy Đồng ban đêm)")
@app_commands.describe(noidung="Nội dung tin nhắn")
async def chat_cmd(i: discord.Interaction, noidung: str):
    g = GAMES.get(i.guild.id)
    p = g.players.get(i.user.id) if g else None
    if not p or not g.can_void_chat(p):
        return await i.response.send_message("Bạn không thể chat Âm Giới lúc này.", ephemeral=True)
    await i.response.send_message("👻 Đã gửi (ẩn danh).", ephemeral=True)
    await g.void_say(p.id, noidung)


@group.command(name="huongdan", description="Hướng dẫn chơi Ma Sói")
async def huongdan(i: discord.Interaction):
    await i.response.send_message(embed=discord.Embed(title="📖 HƯỚNG DẪN CHƠI MA SÓI", description=GUIDE, color=0x3498DB))


@group.command(name="vaitro", description="Danh sách toàn bộ vai trò")
async def vaitro(i: discord.Interaction):
    embeds = []
    for t, title in ((V, "🧑‍🌾 Phe Dân Làng"), (W, "🐺 Phe Ma Sói"), (N, "⚖️ Phe Trung Lập")):
        d = "\n".join(f"{e} **{n}**: {desc}" for n, e, tm, desc in ROLES.values() if tm == t)
        embeds.append(discord.Embed(title=title, description=d[:4000], color=COLOR[t]))
    await i.response.send_message(embeds=embeds, ephemeral=True)


bot.tree.add_command(group)


@bot.event
async def on_voice_state_update(member, before, after):
    g = GAMES.get(member.guild.id)
    if not g or member.id not in g.players or after.channel is None: return
    p = g.players[member.id]
    try:
        if not p.alive and g.void_vc and after.channel.id != g.void_vc.id and g.phase != "end":
            await member.edit(mute=False, voice_channel=g.void_vc)
        elif p.alive and (g.tts or g.phase in ("night", "late")) and not after.mute and after.channel.id != g.void_vc.id:
            await member.edit(mute=True)
    except discord.HTTPException:
        pass


@bot.event
async def on_message(msg):
    """Thầy Đồng gõ vào phòng riêng ban đêm -> bot xóa và đăng lại ẩn danh ở Âm Giới."""
    if msg.author.bot or not msg.guild or not msg.content: return
    g = GAMES.get(msg.guild.id)
    if not g: return
    if g.tts and msg.channel.id == g.text.id and g.phase == "day":
        p = g.players.get(msg.author.id)
        if p and p.alive: g.tts_enqueue(p, msg.content)
        return
    tc = g.role_ch.get("thaydong")
    if not tc or msg.channel.id != tc.id: return
    p = g.players.get(msg.author.id)
    if not p or p.role != "thaydong" or not p.alive or g.phase not in ("night", "late"): return
    try: await msg.delete()
    except discord.HTTPException: pass
    await g.void_say(p.id, msg.content)


@bot.event
async def on_member_update(before, after):
    g = GAMES.get(after.guild.id)
    if not g or g.phase in ("setup", "end") or after.id not in g.players: return
    p = g.players[after.id]
    if after.nick != g.expected_nick(p):
        try: await after.edit(nick=g.expected_nick(p))
        except discord.HTTPException: pass


@bot.event
async def on_ready():
    print(f"Đăng nhập: {bot.user} — sẵn sàng!")


if __name__ == "__main__":
    bot.run(os.environ["DISCORD_TOKEN"])

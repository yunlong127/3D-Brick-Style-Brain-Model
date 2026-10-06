# -*- coding: utf-8 -*-
"""将 AAL 脑图谱转换为前端可用的体素积木 JSON 数据。

输出 public/brain.json：
- dims / spacing
- voxels_b64: base64 编码的 Uint8 数组，每 4 字节一个体素 [right, anterior, superior, regionIndex]
- regions: 每个脑区的中文名/功能列表/协作链路/颜色
"""
import struct
import os
import json
import base64
import colorsys
import numpy as np

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "public")
NII_PATH = os.path.join(DATA_DIR, "ROI_MNI_V4.nii")
TXT_PATH = os.path.join(DATA_DIR, "ROI_MNI_V4.txt")

# ---------------------------------------------------------------- 读取 NIfTI
with open(NII_PATH, "rb") as f:
    blob = f.read()

if struct.unpack_from("<i", blob, 0)[0] == 348:
    endian = "<"
else:
    endian = ">"

dim = struct.unpack_from(endian + "8h", blob, 40)
datatype = struct.unpack_from(endian + "h", blob, 70)[0]
bitpix = struct.unpack_from(endian + "h", blob, 72)[0]
vox_offset = struct.unpack_from(endian + "f", blob, 108)[0]
pixdim = struct.unpack_from(endian + "8f", blob, 76)
srow_x = struct.unpack_from(endian + "4f", blob, 280)
srow_y = struct.unpack_from(endian + "4f", blob, 296)
srow_z = struct.unpack_from(endian + "4f", blob, 312)

nx, ny, nz = dim[1], dim[2], dim[3]
code = {2: "B", 4: "h", 8: "i", 16: "f", 512: "H", 768: "I", 256: "b", 1024: "q", 1280: "Q"}[datatype]
raw = blob[int(vox_offset):]
n = nx * ny * nz
vals = np.array(struct.unpack_from(endian + "%d%s" % (n, code), raw), dtype=np.int32).reshape((nz, ny, nx))

with open(TXT_PATH, "r", encoding="utf-8", errors="replace") as f:
    rows = [ln.split() for ln in f if ln.strip()]

labels = [(r[0], r[1], int(r[2])) for r in rows]

# ---------------------------------------------------------------- 协作链路库
CHAINS = {
    "运动执行链路": "初级运动皮层发出皮质脊髓束，经内囊、脑干下行至脊髓前角，控制对侧骨骼肌的随意运动。",
    "皮质-基底节-丘脑运动环路": "皮层→纹状体→苍白球→丘脑→皮层，构成运动的选择、启动与调节回路。",
    "基底节环路": "尾状核、壳核、苍白球与丘脑、皮层共同构成基底节运动环路，参与动作选择与习惯形成。",
    "运动计划链路": "辅助运动区与前额叶、基底节协同，负责动作序列的规划与启动。",
    "感觉运动整合链路": "中央沟盖与初级感觉/运动皮层协同，将体感信息与运动指令进行整合。",
    "躯体感觉上行通路": "皮肤与本体感受器经脊髓-丘脑束上行至中央后回，加工触觉、痛温觉与本体感觉。",
    "视觉通路": "视网膜→外侧膝状体→初级视觉皮层，实现视觉信息的初级加工。",
    "视网膜-外侧膝状体-皮层通路": "视网膜神经节细胞经外侧膝状体投射到 V1，是视觉信息进入皮层的主通路。",
    "背侧视觉流（空间通路）": "V1→枕上/顶叶，负责空间位置、运动与“在哪里”通路。",
    "腹侧视觉流（物体通路）": "V1→枕下/颞下，负责物体、颜色与“是什么”通路。",
    "听觉通路": "耳蜗→脑干听觉核团→内侧膝状体→颞横回，加工声音的频率与时间特征。",
    "嗅觉通路": "嗅上皮→嗅球→梨状皮质与杏仁核，是唯一不经过丘脑中继的感觉通路。",
    "味觉通路": "味蕾→孤束核→丘脑→岛叶/中央沟盖，加工酸、甜、苦、咸、鲜等味觉。",
    "语言网络": "额下回（Broca 区）、颞上回（Wernicke 区）与弓状束共同构成语言产生与理解网络。",
    "Broca-韦尼克环路": "Broca 区负责语言产出，Wernicke 区负责语言理解，二者经弓状束相连。",
    "阅读链路": "视觉词形区→角回→颞中回，实现文字识别与语义通达。",
    "面孔识别链路": "梭状回面孔区（FFA）与颞中回、枕下回协同，完成面孔的知觉与身份识别。",
    "记忆系统": "海马-海马旁回-内嗅皮层构成情景记忆的编码与提取网络。",
    "海马-皮层记忆环路": "海马将新信息编码后，通过睡眠期重放逐步巩固到新皮层的长时记忆。",
    "情绪记忆链路": "杏仁核-海马协同，为带有情绪色彩的事件赋予情感意义并增强其记忆。",
    "边缘系统": "杏仁核、海马、扣带回与眶额皮层共同构成情绪与动机的神经环路。",
    "眶额-边缘情绪链路": "眶额皮层与杏仁核、脑岛协同，进行奖赏-惩罚评估与情绪决策。",
    "奖赏系统": "腹侧被盖区→伏隔核→前额叶的多巴胺通路，编码奖赏预测与动机。",
    "突显网络": "前脑岛与前扣带回协同，检测并标记环境中显著的内外刺激。",
    "默认模式网络": "后扣带回、楔前叶、内侧前额叶与角回在静息时激活，支持自我参照与心理漫游。",
    "执行控制网络": "前额叶（尤其背外侧）与顶叶协同，支持计划、抑制与工作记忆。",
    "背侧注意网络": "顶上回、额中回与额眼区协同，实现空间注意的自上而下定向。",
    "额顶控制网络": "外侧前额叶与顶下/顶上回协同，支持灵活的任务切换与目标导向行为。",
    "认知控制链路": "前扣带回与外侧前额叶协同，进行冲突监测与认知调控。",
    "内感受链路": "脑岛整合来自内脏与自主神经的信号，形成对身体内部状态的觉察。",
    "疼痛矩阵": "中扣带回、脑岛、丘脑与躯体感觉皮层共同构成痛觉加工的神经网络。",
    "社会认知链路": "颞极、眶额皮层与内侧前额叶协同，支持情绪识别、心理理论与社会判断。",
    "语义记忆链路": "颞中回、颞极与角回协同，储存和提取关于世界的事实性知识。",
    "空间导航链路": "海马、海马旁回与后顶叶协同，构建认知地图并支持空间定位。",
    "镜像神经元系统": "缘上回、额下回与顶下回在观察与模仿他人动作时激活。",
    "视觉记忆链路": "颞下回与梭状回协同，实现对物体形象的识别与视觉记忆。",
    "小脑-大脑认知环路": "小脑脚 I/II 通过丘脑与前额叶相连，参与语言、工作记忆等认知功能。",
    "小脑-脊髓本体感觉环路": "小脑前叶接收脊髓本体感觉传入，参与姿势与运动调节。",
    "小脑运动协调环路": "小脑半球经丘脑-皮层回路参与运动协调、时序与运动学习。",
    "前庭-小脑通路": "前庭核与前庭神经传入绒球小结叶与蚓部，维持平衡与姿势。",
    "眼球运动链路": "小脑蚓部 VII 与前庭核、动眼核团协同，参与眼球运动的协调。",
    "丘脑-皮层环路": "丘脑作为中继站与皮层形成双向连接，参与感觉门控与意识状态。",
    "感觉中继链路": "丘脑将除嗅觉外的感觉信息中继到相应皮层，是感觉上行的重要枢纽。",
}

# ---------------------------------------------------------------- 脑区元数据
# base 名称 -> (中文名, [功能列表], [协作链路])
REGIONS = {
    "Precentral": ("中央前回", ["控制对侧肢体的随意运动", "初级运动皮层（M1），发出皮质脊髓束", "参与精细动作与肌力调节"], ["运动执行链路", "皮质-基底节-丘脑运动环路"]),
    "Frontal_Sup": ("额上回", ["参与高级认知与计划", "维持工作记忆与注意力", "参与眼动控制"], ["执行控制网络", "背侧注意网络"]),
    "Frontal_Sup_Orb": ("眶部额上回", ["参与奖赏评估与决策", "调节情绪反应", "参与社会行为判断"], ["眶额-边缘情绪链路", "奖赏系统"]),
    "Frontal_Mid": ("额中回", ["执行功能与任务切换", "工作记忆的维持", "空间注意与眼动控制"], ["执行控制网络", "额顶控制网络"]),
    "Frontal_Mid_Orb": ("眶部额中回", ["情绪加工与价值判断", "冲动控制"], ["眶额-边缘情绪链路", "奖赏系统"]),
    "Frontal_Inf_Oper": ("岛盖部额下回", ["语言产生（左侧 Broca 区 BA44）", "语法加工", "言语运动控制"], ["语言网络", "Broca-韦尼克环路"]),
    "Frontal_Inf_Tri": ("三角部额下回", ["语义检索", "语言产生（Broca 区 BA45）", "言语工作记忆"], ["语言网络", "Broca-韦尼克环路"]),
    "Frontal_Inf_Orb": ("眶部额下回", ["情绪调控", "社会认知与共情"], ["眶额-边缘情绪链路", "社会认知链路"]),
    "Rolandic_Oper": ("中央沟盖", ["感觉运动整合", "味觉加工", "言语运动控制"], ["感觉运动整合链路", "味觉通路"]),
    "Supp_Motor_Area": ("辅助运动区", ["运动序列规划", "双侧肢体协调", "运动学习"], ["运动计划链路", "皮质-基底节-丘脑运动环路"]),
    "Olfactory": ("嗅皮质", ["嗅觉信息加工", "气味与情绪记忆关联"], ["嗅觉通路", "边缘系统"]),
    "Frontal_Sup_Medial": ("内侧额上回", ["自我参照加工", "心理理论", "默认网络组成部分"], ["默认模式网络", "社会认知链路"]),
    "Frontal_Med_Orb": ("内侧眶额回", ["情绪与奖赏评估", "价值决策", "冲动抑制"], ["眶额-边缘情绪链路", "奖赏系统"]),
    "Rectus": ("直回", ["社会认知", "情绪调控", "抑制控制"], ["眶额-边缘情绪链路", "社会认知链路"]),
    "Insula": ("脑岛", ["内感受觉察", "情绪体验", "突显网络核心枢纽"], ["突显网络", "内感受链路"]),
    "Cingulum_Ant": ("前扣带回", ["冲突监控", "错误检测", "情绪调控"], ["突显网络", "认知控制链路"]),
    "Cingulum_Mid": ("中扣带回", ["认知控制", "疼痛加工", "反应选择"], ["认知控制链路", "疼痛矩阵"]),
    "Cingulum_Post": ("后扣带回", ["默认网络枢纽", "自传体记忆", "空间注意"], ["默认模式网络", "记忆系统"]),
    "Hippocampus": ("海马", ["情景记忆编码与巩固", "空间导航", "模式分离"], ["记忆系统", "海马-皮层记忆环路"]),
    "ParaHippocampal": ("海马旁回", ["场景记忆（旁海马位置区 PPA）", "空间导航", "环境识别"], ["记忆系统", "空间导航链路"]),
    "Amygdala": ("杏仁核", ["恐惧与威胁加工", "情绪记忆巩固", "社会情绪识别"], ["边缘系统", "情绪记忆链路"]),
    "Calcarine": ("距状裂皮层", ["初级视觉加工（V1）", "视觉空间频率加工", "视觉意识基础"], ["视觉通路", "视网膜-外侧膝状体-皮层通路"]),
    "Cuneus": ("楔叶", ["视觉空间加工", "视觉注意", "视觉表象"], ["视觉通路", "背侧视觉流（空间通路）"]),
    "Lingual": ("舌回", ["视觉加工", "阅读（视觉词形加工）", "颜色知觉"], ["视觉通路", "腹侧视觉流（物体通路）"]),
    "Occipital_Sup": ("枕上回", ["视觉空间加工", "运动知觉"], ["背侧视觉流（空间通路）"]),
    "Occipital_Mid": ("枕中回", ["视觉加工", "视觉词形区（VWFA）", "阅读"], ["视觉通路", "阅读链路"]),
    "Occipital_Inf": ("枕下回", ["物体识别", "颜色知觉", "形状知觉"], ["腹侧视觉流（物体通路）"]),
    "Fusiform": ("梭状回", ["面孔识别（FFA）", "阅读（视觉词形）", "物体类别识别"], ["面孔识别链路", "阅读链路"]),
    "Postcentral": ("中央后回", ["对侧触觉加工", "本体感觉", "痛温觉加工"], ["躯体感觉上行通路"]),
    "Parietal_Sup": ("顶上回", ["空间注意", "感觉运动整合", "视觉引导的动作"], ["背侧注意网络", "感觉运动整合链路"]),
    "Parietal_Inf": ("顶下回", ["语言加工", "数学运算", "动作观察"], ["语言网络", "额顶控制网络"]),
    "SupraMarginal": ("缘上回", ["语言（音韵加工）", "模仿", "本体感觉整合"], ["语言网络", "镜像神经元系统"]),
    "Angular": ("角回", ["阅读与书写", "语义加工", "默认网络组成部分"], ["默认模式网络", "阅读链路"]),
    "Precuneus": ("楔前叶", ["自我意识", "视觉空间表象", "情景记忆提取"], ["默认模式网络", "记忆系统"]),
    "Paracentral_Lobule": ("中央旁小叶", ["下肢运动控制", "足部感觉加工", "括约肌控制"], ["运动执行链路", "躯体感觉上行通路"]),
    "Caudate": ("尾状核", ["运动控制", "奖赏预测", "程序性学习"], ["基底节环路", "奖赏系统"]),
    "Putamen": ("壳核", ["运动执行", "习惯与技能学习", "动作选择"], ["基底节环路", "运动执行链路"]),
    "Pallidum": ("苍白球", ["基底节输出核团", "运动调节", "肌张力调控"], ["基底节环路"]),
    "Thalamus": ("丘脑", ["感觉中继（嗅觉除外）", "意识与唤醒", "注意门控"], ["感觉中继链路", "丘脑-皮层环路"]),
    "Heschl": ("颞横回", ["初级听觉加工（A1）", "音高与频率加工"], ["听觉通路"]),
    "Temporal_Sup": ("颞上回", ["听觉加工", "语言理解（Wernicke 区）", "社会声音加工"], ["听觉通路", "语言网络"]),
    "Temporal_Pole_Sup": ("颞极颞上回", ["社会情绪加工", "语义记忆", "人名与面孔联想"], ["语义记忆链路", "社会认知链路"]),
    "Temporal_Mid": ("颞中回", ["语义加工", "面孔知觉", "词汇通达"], ["语义记忆链路", "面孔识别链路"]),
    "Temporal_Pole_Mid": ("颞极颞中回", ["语义记忆", "社会认知", "多模态概念整合"], ["语义记忆链路", "社会认知链路"]),
    "Temporal_Inf": ("颞下回", ["物体识别", "视觉记忆", "复杂形状加工"], ["腹侧视觉流（物体通路）", "视觉记忆链路"]),
    "Cerebellum_Crus1": ("小脑脚 I", ["语言加工", "工作记忆", "认知控制"], ["小脑-大脑认知环路"]),
    "Cerebellum_Crus2": ("小脑脚 II", ["工作记忆", "认知灵活性"], ["小脑-大脑认知环路"]),
    "Cerebellum_3": ("小脑 III 小叶", ["本体感觉", "躯干运动协调"], ["小脑-脊髓本体感觉环路"]),
    "Cerebellum_4_5": ("小脑 IV-V 小叶", ["躯干运动协调", "肢体运动"], ["小脑运动协调环路"]),
    "Cerebellum_6": ("小脑 VI 小叶", ["肢体运动协调", "运动学习"], ["小脑运动协调环路"]),
    "Cerebellum_7b": ("小脑 VIIb 小叶", ["运动执行", "运动时序"], ["小脑运动协调环路"]),
    "Cerebellum_8": ("小脑 VIII 小叶", ["运动执行", "平衡控制"], ["小脑运动协调环路"]),
    "Cerebellum_9": ("小脑 IX 小叶", ["前庭功能", "平衡维持"], ["前庭-小脑通路"]),
    "Cerebellum_10": ("小脑 X 小叶（绒球小结叶）", ["前庭眼动反射", "平衡与姿势"], ["前庭-小脑通路"]),
    "Vermis_1_2": ("小脑蚓部 I-II", ["躯干姿势控制", "轴向肌张力"], ["小脑运动协调环路"]),
    "Vermis_3": ("小脑蚓部 III", ["姿势控制", "躯干运动"], ["小脑运动协调环路"]),
    "Vermis_4_5": ("小脑蚓部 IV-V", ["躯干运动协调", "姿势调整"], ["小脑运动协调环路"]),
    "Vermis_6": ("小脑蚓部 VI", ["躯干与肢体协调", "姿势稳定"], ["小脑运动协调环路"]),
    "Vermis_7": ("小脑蚓部 VII", ["眼球运动协调", "姿势控制"], ["眼球运动链路", "小脑运动协调环路"]),
    "Vermis_8": ("小脑蚓部 VIII", ["姿势控制", "平衡"], ["小脑运动协调环路"]),
    "Vermis_9": ("小脑蚓部 IX", ["前庭功能", "平衡维持"], ["前庭-小脑通路"]),
    "Vermis_10": ("小脑蚓部 X", ["前庭功能", "平衡维持"], ["前庭-小脑通路"]),
}

# ---------------------------------------------------------------- 颜色生成
def base_name(name):
    if name.endswith("_L") or name.endswith("_R"):
        return name[:-2]
    return name

# 功能分组：相近功能的脑区归入同一色相族（同一色系）
GROUPS = {
    0: ["Precentral", "Frontal_Sup", "Frontal_Sup_Orb", "Frontal_Mid", "Frontal_Mid_Orb",
        "Frontal_Inf_Oper", "Frontal_Inf_Tri", "Frontal_Inf_Orb", "Rolandic_Oper",
        "Supp_Motor_Area", "Olfactory", "Frontal_Sup_Medial", "Frontal_Med_Orb", "Rectus",
        "Paracentral_Lobule"],
    1: ["Postcentral", "Parietal_Sup", "Parietal_Inf", "SupraMarginal", "Angular", "Precuneus"],
    2: ["Calcarine", "Cuneus", "Lingual", "Occipital_Sup", "Occipital_Mid", "Occipital_Inf", "Fusiform"],
    3: ["Heschl", "Temporal_Sup", "Temporal_Pole_Sup", "Temporal_Mid", "Temporal_Pole_Mid", "Temporal_Inf"],
    4: ["Insula", "Cingulum_Ant", "Cingulum_Mid", "Cingulum_Post", "Hippocampus", "ParaHippocampal", "Amygdala"],
    5: ["Caudate", "Putamen", "Pallidum", "Thalamus"],
    6: ["Cerebellum_Crus1", "Cerebellum_Crus2", "Cerebellum_3", "Cerebellum_4_5",
        "Cerebellum_6", "Cerebellum_7b", "Cerebellum_8", "Cerebellum_9", "Cerebellum_10"],
    7: ["Vermis_1_2", "Vermis_3", "Vermis_4_5", "Vermis_6", "Vermis_7", "Vermis_8", "Vermis_9", "Vermis_10"],
}
GROUP_HUES = {0: 0, 1: 45, 2: 90, 3: 135, 4: 180, 5: 225, 6: 270, 7: 315}

base_to_group = {}
for gi, bases in GROUPS.items():
    for k, b in enumerate(bases):
        base_to_group[b] = (gi, k, len(bases))

name_to_rid = {en: i + 1 for i, (code, en, lab) in enumerate(labels)}

# 标签 -> 脑区索引
max_label = max(r[2] for r in labels)
lut = np.zeros(max_label + 1, dtype=np.int32)
for i, (code, en, lab) in enumerate(labels):
    lut[lab] = i + 1

# 体素邻接关系（共享面）→ 用于保证相邻脑区有对比度
adj = set()
for axis in range(3):
    a0 = np.take(vals, np.arange(1, vals.shape[axis]), axis=axis)
    a1 = np.take(vals, np.arange(0, vals.shape[axis] - 1), axis=axis)
    mask = (a0 != 0) & (a1 != 0) & (a0 != a1)
    l0 = a0[mask]
    l1 = a1[mask]
    for x, y in zip(l0.tolist(), l1.tolist()):
        ra, rb = int(lut[x]), int(lut[y])
        adj.add((min(ra, rb), max(ra, rb)))

adj_list = {}
for a, b in adj:
    adj_list.setdefault(a, set()).add(b)
    adj_list.setdefault(b, set()).add(a)

# 加入左/右同源脑区之间的“对比边”，确保同名脑区左右也不同色
for i, (code, en, lab) in enumerate(labels):
    rid = i + 1
    base = base_name(en)
    if en.endswith("_L") or en.endswith("_R"):
        mate = (base + "_R") if en.endswith("_L") else (base + "_L")
        if mate in name_to_rid:
            adj_list.setdefault(rid, set()).add(name_to_rid[mate])
            adj_list.setdefault(name_to_rid[mate], set()).add(rid)

# 图着色分配明度：相邻脑区与左右同源脑区明度都不同（保证对比度）
LEVELS = [0.86, 0.79, 0.72, 0.65, 0.58, 0.51, 0.44, 0.37, 0.30]
lightness = {}
for rid in range(1, len(labels) + 1):
    used = {lightness[nb] for nb in adj_list.get(rid, ()) if nb in lightness}
    chosen = next((lv for lv in LEVELS if lv not in used), None)
    if chosen is None:
        def sep(lv):
            ds = [abs(lv - lightness[nb]) for nb in adj_list.get(rid, ()) if nb in lightness]
            return min(ds) if ds else 1.0
        chosen = max(LEVELS, key=sep)
    lightness[rid] = chosen

def hsl_hex(h, s, l):
    r, g, b = colorsys.hls_to_rgb((h % 360.0) / 360.0, l, s)
    return "#%02x%02x%02x" % (round(r * 255), round(g * 255), round(b * 255))

def color_for(name):
    base = base_name(name)
    gi, k, total = base_to_group[base]
    center = GROUP_HUES[gi]
    step = min(30.0, 40.0 / max(total - 1, 1))
    spread = (k - (total - 1) / 2.0) * step
    side = 2.0 if name.endswith("_L") else (-2.0 if name.endswith("_R") else 0.0)
    h = center + spread + side
    return hsl_hex(h, 0.80, lightness[name_to_rid[name]])

worst = min((abs(lightness[a] - lightness[b]) for a, b in adj), default=1.0)
print("邻接脑区对数:", len(adj), "相邻明度最小差:", round(worst, 3))

# ---------------------------------------------------------------- 构建 regions
regions_out = []
for i, (code, en, lab) in enumerate(labels):
    idx = i + 1
    base = base_name(en)
    zh, funcs, nets = REGIONS[base]
    side = ""
    if en.endswith("_L"):
        side = "（左）"
    elif en.endswith("_R"):
        side = "（右）"
    regions_out.append({
        "id": idx,
        "label": lab,
        "code": code,
        "en": en,
        "name": zh + side,
        "functions": funcs,
        "chains": [{"name": n, "desc": CHAINS[n]} for n in nets],
        "color": color_for(en),
    })

# ---------------------------------------------------------------- 提取体素
M = np.array([[srow_x[0], srow_x[1], srow_x[2]],
              [srow_y[0], srow_y[1], srow_y[2]],
              [srow_z[0], srow_z[1], srow_z[2]]], dtype=np.float64)

world_axis_of = {}
for c in range(3):
    col = M[:, c]
    r = int(np.argmax(np.abs(col)))
    s = 1 if col[r] >= 0 else -1
    world_axis_of[r] = (c, s)

src_ranges = [nx, ny, nz]

coords = np.argwhere(vals != 0)
k_idx, j_idx, i_idx = coords[:, 0], coords[:, 1], coords[:, 2]
src_arrays = {0: i_idx, 1: j_idx, 2: k_idx}
region_idx = lut[vals[k_idx, j_idx, i_idx]]

def world_index(r):
    c, s = world_axis_of[r]
    idx = src_arrays[c]
    if s < 0:
        idx = (src_ranges[c] - 1) - idx
    return idx

right = world_index(0)
anterior = world_index(1)
superior = world_index(2)

new_dims = [src_ranges[world_axis_of[0][0]],
            src_ranges[world_axis_of[1][0]],
            src_ranges[world_axis_of[2][0]]]

N = len(right)
buf = bytearray(N * 4)
buf[0::4] = right.astype(np.uint8).tobytes()
buf[1::4] = anterior.astype(np.uint8).tobytes()
buf[2::4] = superior.astype(np.uint8).tobytes()
buf[3::4] = region_idx.astype(np.uint8).tobytes()

voxels_b64 = base64.b64encode(bytes(buf)).decode("ascii")

counts = {}
for r in region_idx:
    counts[int(r)] = counts.get(int(r), 0) + 1
for r in regions_out:
    r["count"] = counts.get(r["id"], 0)

out = {
    "dims": new_dims,
    "spacing": float(pixdim[1]),
    "voxelCount": N,
    "voxels_b64": voxels_b64,
    "regions": regions_out,
}

os.makedirs(OUT_DIR, exist_ok=True)
out_path = os.path.join(OUT_DIR, "brain.json")
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, separators=(",", ":"))

print("脑区数量:", len(regions_out))
print("体素总数:", N)
print("JSON 大小: %.2f MB" % (os.path.getsize(out_path) / 1024 / 1024))
print("输出:", out_path)

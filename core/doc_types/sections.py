"""Canonical schemas for type-specific sections (the extra_data contract).

Both backend families (cloud DocType formatters and local parsers) must
emit these exact section keys and field names so that:

  * ``Invoice.extra_data`` has one stable shape per doc type
  * the detail-page renderer can display every section generically
  * adding a new doc type = declaring a new schema here + populating it
    from the backend formatters

Sections are plain dicts keyed by human-readable Chinese labels (these
are display names — the UI renders them as table rows).

``extra_data`` JSON shape (see app/utils.py):

    {
      "v": 1,                     # DocType.extra_schema_version
      "sections": {
        "医保信息": { "医保类型": "...", ... },   # medical
        "乘车信息": { "车次": "G1234", ... },    # train
      }
    }
"""

# ---------------------------------------------------------------------------
# Medical (医疗票据) — section "医保信息"
# ---------------------------------------------------------------------------

#: Canonical field order for the medical 医保信息 section. Field names are
#: the display labels; values are the raw OCR strings.
MEDICAL_SECTION_FIELDS: tuple[str, ...] = (
    "发票名称",
    "发票类型",
    "发票属地",
    "医疗机构类型",
    "医保类型",
    "医保编号",
    "性别",
    "医保统筹基金支付",
    "个人账户支付",
    "其他支付",
    "个人现金支付",
    "个人自付",
    "个人自费",
    "就诊日期",
    "收款单位",
    "收款人",
    "交款人",
    "交款人统一社会信用代码",
)

# ---------------------------------------------------------------------------
# Train (铁路电子客票) — section "乘车信息"
# ---------------------------------------------------------------------------

#: Canonical field order for the train 乘车信息 section.
TRAIN_SECTION_FIELDS: tuple[str, ...] = (
    "车次",
    "出发站",
    "到达站",
    "出发时间",
    "座位号",
    "席别",
    "电子客票号",
    "售票站",
    "乘车人",
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def normalize_section(
    raw: dict,
    canonical_fields: tuple[str, ...],
) -> dict:
    """Return only the canonical fields present in ``raw``, in canonical
    order. Unknown keys are dropped (they don't belong to the schema).
    """
    out: dict[str, str] = {}
    for f in canonical_fields:
        v = raw.get(f)
        if v:
            out[f] = str(v)
    return out

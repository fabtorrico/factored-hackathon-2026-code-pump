import hashlib
import json
import random
from pathlib import Path
from typing import Any

from app.ml.labels import IncidentLabel

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "evaluation" / "incident_understanding"
DATA_DIR.mkdir(parents=True, exist_ok=True)
SEED = 42
random.seed(SEED)

FAMILIES: list[dict[str, Any]] = []
fam_idx = 0

# PENDING_OR_DELAYED - 12 families
for i in range(12):
    es_bases = [
        "Mi transferencia todavia no llega a destino.",
        "La transferencia lleva horas sin llegar.",
        "Todavia estoy esperando que llegue la transferencia.",
        "La transferencia esta tardando mucho.",
        "Mi pago todavia no aparece como realizado.",
        "Llevo esperando la transferencia desde hace horas.",
    ]
    pt_bases = [
        "A minha transferencia ainda nao chegou ao destino.",
        "A transferencia esta demorando muito.",
        "Ainda estou a espera que a transferencia chegue.",
        "O meu pagamento ainda nao apareceu como realizado.",
        "Ha horas que espero pela transferencia.",
        "A transferencia ainda nao chegou.",
    ]
    es = es_bases[i % len(es_bases)]
    pt = pt_bases[i % len(pt_bases)]
    FAMILIES.append(
        {
            "family_id": f"fam_{fam_idx:03d}",
            "label": IncidentLabel.PENDING_OR_DELAYED,
            "variants": [
                {"lang": "es", "text": es, "difficulty": "easy"},
                {"lang": "pt", "text": pt, "difficulty": "easy"},
                {
                    "lang": "es",
                    "text": es.replace("transferencia", "transaccion"),
                    "difficulty": "medium",
                },
                {
                    "lang": "pt",
                    "text": pt.replace("transferencia", "transferência"),
                    "difficulty": "medium",
                },
            ],
        }
    )
    fam_idx += 1
# FAILED_OR_DECLINED - 12 families
for i in range(12):
    es_bases = [
        "Mi transferencia fue rechazada.",
        "El pago me salio rechazado.",
        "Me aparece que la transaccion fue declinada.",
        "Intente hacer una transferencia y fue denegada.",
        "La operacion fue rechazada.",
        "Mi compra fue rechazada.",
    ]
    pt_bases = [
        "A minha transferencia foi recusada.",
        "O pagamento foi rejeitado.",
        "A transacao foi declinada.",
        "Tentei fazer uma transferencia e foi negada.",
        "A operacao foi rejeitada.",
        "A minha compra foi recusada.",
    ]
    es = es_bases[i % len(es_bases)]
    pt = pt_bases[i % len(pt_bases)]
    FAMILIES.append(
        {
            "family_id": f"fam_{fam_idx:03d}",
            "label": IncidentLabel.FAILED_OR_DECLINED,
            "variants": [
                {"lang": "es", "text": es, "difficulty": "easy"},
                {"lang": "pt", "text": pt, "difficulty": "easy"},
                {"lang": "es", "text": es + " Por que?", "difficulty": "medium"},
                {"lang": "pt", "text": pt + " Porque?", "difficulty": "medium"},
            ],
        }
    )
    fam_idx += 1
# REVERSED - 8 families
for i in range(8):
    es_bases = [
        "Me devolvieron el dinero de la transferencia.",
        "La transferencia fue revertida.",
        "Me reembolsaron el pago.",
        "La operacion fue anulada y me devolvieron el dinero.",
    ]
    pt_bases = [
        "Devolveram-me o dinheiro da transferencia.",
        "A transferencia foi revertida.",
        "Fui reembolsado pelo pagamento.",
        "A operacao foi anulada e devolveram-me o dinheiro.",
    ]
    es = es_bases[i % len(es_bases)]
    pt = pt_bases[i % len(pt_bases)]
    FAMILIES.append(
        {
            "family_id": f"fam_{fam_idx:03d}",
            "label": IncidentLabel.REVERSED,
            "variants": [
                {"lang": "es", "text": es, "difficulty": "easy"},
                {"lang": "pt", "text": pt, "difficulty": "easy"},
                {"lang": "es", "text": "Me han devuelto el dinero.", "difficulty": "easy"},
                {"lang": "pt", "text": "Deram-me o dinheiro de volta.", "difficulty": "medium"},
            ],
        }
    )
    fam_idx += 1

# APPROVED_BUT_UNRESOLVED - 10 families
for i in range(10):
    es_bases = [
        "La transferencia aparece aprobada pero el dinero no llega.",
        "El pago fue aprobado pero no recibí el dinero.",
        "Aparece aprobado pero todavía no tengo el dinero.",
        "Dice aprobado pero el beneficiario no lo recibió.",
    ]
    pt_bases = [
        "A transferencia aparece aprovada mas o dinheiro nao chegou.",
        "O pagamento foi aprovado mas nao recebi o dinheiro.",
        "Aparece aprovado mas ainda nao tenho o dinheiro.",
        "Diz aprovado mas o destinatario nao recebeu.",
    ]
    es = es_bases[i % len(es_bases)]
    pt = pt_bases[i % len(pt_bases)]
    FAMILIES.append(
        {
            "family_id": f"fam_{fam_idx:03d}",
            "label": IncidentLabel.APPROVED_BUT_UNRESOLVED,
            "variants": [
                {"lang": "es", "text": es, "difficulty": "medium"},
                {"lang": "pt", "text": pt, "difficulty": "medium"},
                {
                    "lang": "es",
                    "text": es.replace("aprobada", "aprobada").replace("dinero", "importe"),
                    "difficulty": "hard",
                },
                {"lang": "pt", "text": pt, "difficulty": "hard"},
            ],
        }
    )
    fam_idx += 1
# AMBIGUOUS_TRANSACTION - 10 families
for i in range(10):
    es_bases = [
        "No sé si la transferencia se hizo.",
        "No estoy seguro si el pago fue enviado.",
        "No me queda claro qué pasó con la transferencia.",
        "No sé si se envió o no el dinero.",
        "Estoy confundido sobre el estado de la transferencia.",
    ]
    pt_bases = [
        "Nao sei se a transferencia foi feita.",
        "Nao estou seguro se o pagamento foi enviado.",
        "Nao esta claro o que aconteceu com a transferencia.",
        "Nao sei se o dinheiro foi enviado ou nao.",
        "Estou confuso sobre o estado da transferencia.",
    ]
    es = es_bases[i % len(es_bases)]
    pt = pt_bases[i % len(pt_bases)]
    FAMILIES.append(
        {
            "family_id": f"fam_{fam_idx:03d}",
            "label": IncidentLabel.AMBIGUOUS_TRANSACTION,
            "variants": [
                {"lang": "es", "text": es, "difficulty": "medium"},
                {"lang": "pt", "text": pt, "difficulty": "medium"},
                {
                    "lang": "es",
                    "text": es.replace("transferencia", "operacion"),
                    "difficulty": "hard",
                },
                {
                    "lang": "pt",
                    "text": pt.replace("transferencia", "operacao"),
                    "difficulty": "hard",
                },
            ],
        }
    )
    fam_idx += 1

# OUT_OF_SCOPE - 10 families
for i in range(10):
    es_bases = [
        "Quisiera saber el tipo de cambio de hoy.",
        "Necesito abrir una nueva cuenta.",
        "Como puedo solicitar una tarjeta de credito?",
        "Cual es el horario de la sucursal?",
        "Quisiera cambiar mi clave de acceso.",
        "Necesito informacion sobre prestamos.",
    ]
    pt_bases = [
        "Gostaria de saber a taxa de cambio de hoje.",
        "Preciso abrir uma nova conta.",
        "Como posso solicitar um cartao de credito?",
        "Qual e o horario da agencia?",
        "Gostaria de alterar a minha senha.",
        "Preciso de informacao sobre emprestimos.",
    ]
    es = es_bases[i % len(es_bases)]
    pt = pt_bases[i % len(pt_bases)]
    FAMILIES.append(
        {
            "family_id": f"fam_{fam_idx:03d}",
            "label": IncidentLabel.OUT_OF_SCOPE,
            "variants": [
                {"lang": "es", "text": es, "difficulty": "easy"},
                {"lang": "pt", "text": pt, "difficulty": "easy"},
                {"lang": "es", "text": es + " Gracias.", "difficulty": "easy"},
                {"lang": "pt", "text": pt + " Obrigado.", "difficulty": "easy"},
            ],
        }
    )
    fam_idx += 1


def make_example(
    family_id: str,
    label: IncidentLabel,
    lang: str,
    text: str,
    difficulty: str = "easy",
    variant_index: int = 0,
) -> dict[str, Any]:
    h = hashlib.md5(f"{family_id}:{lang}:{variant_index}:{text}".encode()).hexdigest()[:8]
    return {
        "id": f"ex_{family_id}_{lang}_{variant_index:02d}_{h}",
        "text": text,
        "language": lang,
        "label": label.value,
        "semantic_family": family_id,
        "difficulty": difficulty,
    }


# Build examples, dropping exact duplicate (lang, text) variants inside a family.
examples = []
for fam in FAMILIES:
    seen: set[tuple[str, str]] = set()
    for var in fam["variants"]:
        key = (var["lang"], var["text"])
        if key in seen:
            continue
        seen.add(key)
        examples.append(
            make_example(
                fam["family_id"],
                fam["label"],
                var["lang"],
                var["text"],
                var.get("difficulty", "easy"),
                len(seen) - 1,
            )
        )

# Deterministic shuffle
random.shuffle(examples)

# Group-aware split by semantic family, stratified by label so that every class
# is represented in every split (a global family split can leave a class out of
# a split). Families are never shared across splits.
label_families: dict[str, list[str]] = {}
for fam in FAMILIES:
    label_families.setdefault(fam["label"].value, []).append(fam["family_id"])

train_f: set[str] = set()
dev_f: set[str] = set()
test_f: set[str] = set()
for label in sorted(label_families):
    fams = sorted(label_families[label])
    random.shuffle(fams)
    count = len(fams)
    # Guarantee at least one family per class in dev and test for coverage.
    test_count = max(1, int(round(count * 0.15)))
    dev_count = max(1, int(round(count * 0.15)))
    test_count = min(test_count, max(1, count - 2))
    dev_count = min(dev_count, max(1, count - test_count - 1))
    test_f.update(fams[:test_count])
    dev_f.update(fams[test_count : test_count + dev_count])
    train_f.update(fams[test_count + dev_count :])

n = sum(len(v) for v in label_families.values())
all_families = sorted(train_f | dev_f | test_f)

train = [e for e in examples if e["semantic_family"] in train_f]
dev = [e for e in examples if e["semantic_family"] in dev_f]
test = [e for e in examples if e["semantic_family"] in test_f]

dataset = {
    "metadata": {
        "seed": SEED,
        "description": (
            "Team-generated synthetic task-specific evaluation dataset "
            "(no organizer records, no PII)."
        ),
        "split": "group-aware by semantic_family",
        "version": "1.0.0",
        "total": len(examples),
        "train": len(train),
        "dev": len(dev),
        "test": len(test),
        "num_families": n,
    },
    "train": train,
    "dev": dev,
    "test": test,
    "examples": examples,
}

# Write files
(DATA_DIR / "dataset.json").write_text(
    json.dumps(dataset, ensure_ascii=False, indent=2), encoding="utf-8"
)
(DATA_DIR / "splits.json").write_text(
    json.dumps(
        {
            "seed": SEED,
            "train_families": sorted(train_f),
            "dev_families": sorted(dev_f),
            "test_families": sorted(test_f),
            "num_families": n,
        },
        ensure_ascii=False,
        indent=2,
    ),
    encoding="utf-8",
)

print(f"Total: {len(examples)}, train={len(train)}, dev={len(dev)}, test={len(test)}, families={n}")

"""Independently authored Challenge Set v2 families for REVERSED."""

LABEL = "REVERSED"

FAMILIES = [
    (
        "v2rev_es_01",
        "DIRECT",
        "es",
        [
            "Me devolvieron la plata de la compra de ayer.",
            "El pago se revirtio y el monto volvio a mi cuenta.",
            "Me reintegraron el valor sin que yo lo pidiera.",
            "La operacion fue anulada y me regresaron el dinero.",
        ],
    ),
    (
        "v2rev_es_02",
        "DIRECT",
        "es",
        [
            "Primero me cobraron y despues me lo devolvieron.",
            "El cobro se cayo y quedo revertido.",
            "Me hicieron el cargo y luego lo anularon.",
            "Se genero el pago y despues se revirtio.",
        ],
    ),
    (
        "v2rev_es_03",
        "DIRECT",
        "es",
        [
            "Me reembolsaron despues de reclamar el pago.",
            "Ya salio el reembolso a mi favor.",
            "El comercio me devolvio el dinero.",
            "Acreditaron de vuelta el monto de la compra.",
        ],
    ),
    (
        "v2rev_es_04",
        "INDIRECT",
        "es",
        [
            "El dinero que me habian cobrado aparecio de nuevo en mi cuenta.",
            "Pague y al rato otra vez tenia el saldo de antes.",
            "Me lo cobraron y despues desaparecio el cargo.",
            "El monto volvio solo, ya no aparece el cobro.",
        ],
    ),
    (
        "v2rev_es_05",
        "INDIRECT",
        "es",
        [
            "Se hizo el pago y mas tarde lo cancelaron desde el banco.",
            "La compra se concreto y luego la dejaron sin efecto.",
            "Me descontaron y al final sin efecto, otra vez lo tengo.",
            "El movimiento se genero y despues lo dieron por cancelado.",
        ],
    ),
    (
        "v2rev_es_06",
        "HARD_NEGATIVE",
        "es",
        [
            "Aunque algunos intentos salieron rechazados, el que si se cobro me lo devolvieron despues.",  # noqa: E501
            "El pago no salio rechazado, se hizo y luego me lo revirtieron.",
            "No fue un rechazo, me lo cobraron y despues lo anularon.",
            "Paso como rechazado un intento, pero el cobro real me lo devolvieron.",
        ],
    ),
    (
        "v2rev_es_07",
        "HARD_NEGATIVE",
        "es",
        [
            "Estuvo pendiente un rato y al final me lo devolvieron.",
            "Lo vi pendiente y despues aparece el reintegro.",
            "Pense que seguia pendiente pero ya me lo revirtieron.",
            "Quedo pendiente y luego me lo devolvieron.",
        ],
    ),
    (
        "v2rev_es_08",
        "LEXICAL_OVERLAP",
        "es",
        [
            "El pago fue aprobado pero despues me devolvieron el monto.",
            "Aprobaron la compra y luego la reversaron.",
            "Me aparece aprobado y a la vez el reembolso.",
            "Fue aprobado un momento y enseguida lo devolvieron.",
        ],
    ),
    (
        "v2rev_es_09",
        "COLLOQUIAL_OR_NOISY",
        "es",
        [
            "me devolvieron la plata de la compra q hise ayer",
            "el cobro se cayo y me llego la plata de vuelta",
            "me reintegraron el monto, menos mal",
            "me anularon la compra y ya tengo mi plata",
        ],
    ),
    (
        "v2rev_es_10",
        "COLLOQUIAL_OR_NOISY",
        "es",
        [
            "Menos mal, ya me devolvieron la plata.",
            "Me regresaron el cobro, todo bien.",
            "Ya me llego el reembolso, gracias.",
            "Me quitaron el cargo, ya quede.",
        ],
    ),
    (
        "v2rev_es_11",
        "LOW_CONTEXT",
        "es",
        [
            "Me lo devolvieron.",
            "Se revirtio.",
            "Ya hay reembolso.",
            "Me regresaron el monto.",
        ],
    ),
    (
        "v2rev_es_12",
        "LOW_CONTEXT",
        "es",
        [
            "Cargo anulado.",
            "Pago devuelto.",
            "Monto reintegrado.",
            "Operacion revertida.",
        ],
    ),
    (
        "v2rev_es_13",
        "INDIRECT",
        "es",
        [
            "Ese cobro que me hicieron ya no esta, lo quitaron.",
            "Me sacaron el dinero y despues me lo pusieron otra vez.",
            "El banco deshizo el cobro solo.",
            "El cargo desaparecio y el saldo regreso.",
        ],
    ),
    (
        "v2rev_pt_14",
        "DIRECT",
        "pt",
        [
            "Me devolveram o dinheiro da compra de ontem.",
            "O pagamento foi revertido e o valor voltou pra minha conta.",
            "Me reembolsaram o valor sem eu pedir.",
            "A operacao foi anulada e me devolveram o dinheiro.",
        ],
    ),
    (
        "v2rev_pt_15",
        "DIRECT",
        "pt",
        [
            "Primeiro me cobraram e depois me devolveram.",
            "A cobranca caiu e ficou revertida.",
            "Fizeram o lancamento e depois anularam.",
            "O pagamento foi gerado e depois revertido.",
        ],
    ),
    (
        "v2rev_pt_16",
        "DIRECT",
        "pt",
        [
            "Me reembolsaram depois que reclamei o pagamento.",
            "O estorno ja saiu a meu favor.",
            "A loja me devolveu o dinheiro.",
            "Creditaram de volta o valor da compra.",
        ],
    ),
    (
        "v2rev_pt_17",
        "INDIRECT",
        "pt",
        [
            "O dinheiro que tinham me cobrado apareceu de novo na conta.",
            "Paguei e depois tinha o saldo de antes outra vez.",
            "Me cobraram e depois a cobranca sumiu.",
            "O valor voltou sozinho, o lancamento nao aparece mais.",
        ],
    ),
    (
        "v2rev_pt_18",
        "INDIRECT",
        "pt",
        [
            "O pagamento foi feito e mais tarde cancelaram pelo banco.",
            "A compra se concretizou e depois deixaram sem efeito.",
            "Me descontaram e no fim sem efeito, tenho de volta.",
            "O movimento foi gerado e depois deram como cancelado.",
        ],
    ),
    (
        "v2rev_pt_19",
        "HARD_NEGATIVE",
        "pt",
        [
            "Algumas tentativas deram recusado, mas a que passou me devolveram depois.",
            "O pagamento nao saiu recusado, foi feito e depois reverteram.",
            "Nao foi recusado, me cobraram e depois anularam.",
            "Deu recusado numa tentativa, mas a cobranca real me devolveram.",
        ],
    ),
    (
        "v2rev_pt_20",
        "HARD_NEGATIVE",
        "pt",
        [
            "Ficou pendente um tempo e no fim me devolveram.",
            "Vi pendente e depois aparece o estorno.",
            "Achei que ainda estava pendente mas ja reverteram.",
            "Ficou pendente e depois me devolveram.",
        ],
    ),
    (
        "v2rev_pt_21",
        "LEXICAL_OVERLAP",
        "pt",
        [
            "O pagamento foi aprovado mas depois me devolveram o valor.",
            "Aprovaram a compra e depois reverteram.",
            "Aparece aprovado e ao mesmo tempo o estorno.",
            "Foi aprovado por um momento e logo devolveram.",
        ],
    ),
    (
        "v2rev_pt_22",
        "COLLOQUIAL_OR_NOISY",
        "pt",
        [
            "me devolveram a grana da compra q fiz ontem",
            "a cobranca caiu e o dinheiro voltou",
            "me estornaram o valor, ainda bem",
            "anularam minha compra e ja tenho meu dinheiro",
        ],
    ),
    (
        "v2rev_pt_23",
        "COLLOQUIAL_OR_NOISY",
        "pt",
        [
            "Ainda bem, ja me devolveram a grana.",
            "Me voltaram a cobranca, tudo certo.",
            "Ja chegou o estorno, valeu.",
            "Tiraram a cobranca, to tranquilo.",
        ],
    ),
    (
        "v2rev_pt_24",
        "LOW_CONTEXT",
        "pt",
        [
            "Me devolveram.",
            "Foi revertido.",
            "Ja tem estorno.",
            "Me voltaram o valor.",
        ],
    ),
    (
        "v2rev_pt_25",
        "LOW_CONTEXT",
        "pt",
        [
            "Cobranca anulada.",
            "Pagamento devolvido.",
            "Valor estornado.",
            "Operacao revertida.",
        ],
    ),
]

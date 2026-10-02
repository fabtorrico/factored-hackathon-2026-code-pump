"""Independently authored Challenge Set v2 families for AMBIGUOUS_TRANSACTION.

AMBIGUOUS_TRANSACTION is a semantic class: the customer has an incident but does not
identify which transaction, or several transactions plausibly match. It is NOT model
abstention.
"""

LABEL = "AMBIGUOUS_TRANSACTION"

FAMILIES = [
    (
        "v2amb_es_01",
        "DIRECT",
        "es",
        [
            "Tengo un problema con un pago pero no se cual de todos.",
            "No estoy seguro de cual de mis movimientos es el que fallo.",
            "Me paso algo con una de mis transferencias, no se cual.",
            "Hay varias operaciones y no identifico la del problema.",
        ],
    ),
    (
        "v2amb_es_02",
        "DIRECT",
        "es",
        [
            "Puede ser el pago de ayer o el de antes de ayer, no se cual.",
            "Tengo dos cobros parecidos y no se cual es el malo.",
            "Entre dos movimientos iguales no se cual tuvo el problema.",
            "No logro distinguir cual de los dos pagos es.",
        ],
    ),
    (
        "v2amb_es_03",
        "DIRECT",
        "es",
        [
            "Tuve un problema con una operacion pero no se el numero.",
            "Algo salio mal con un pago, no recuerdo cual.",
            "Un movimiento me dio problema y no se cual es.",
            "Se me presento un inconveniente, no se que operacion fue.",
        ],
    ),
    (
        "v2amb_es_04",
        "INDIRECT",
        "es",
        [
            "Alguna de mis compras de esta semana no cuadra, no se cual.",
            "Creo que me cobraron algo raro, no se que movimiento.",
            "Me falta plata y no se de que operacion.",
            "Algo no cuadra en mis movimientos, no se cual.",
        ],
    ),
    (
        "v2amb_es_05",
        "INDIRECT",
        "es",
        [
            "Hice varios envios seguidos y uno no cuadra, no se cual.",
            "Tengo dos retiros el mismo dia y no se cual me fallo.",
            "Varios pagos iguales y uno es el problematico, no se cual.",
            "No se cual de los envios que hice tuvo el problema.",
        ],
    ),
    (
        "v2amb_es_06",
        "HARD_NEGATIVE",
        "es",
        [
            "Hay algo pendiente pero no se cual de mis pagos es.",
            "Una operacion quedo pendiente y no se cual.",
            "Me sale algo pendiente y no identifico el movimiento.",
            "Tengo un pendiente, no se cual.",
        ],
    ),
    (
        "v2amb_es_07",
        "HARD_NEGATIVE",
        "es",
        [
            "Me rechazaron algo pero no se cual de los pagos.",
            "Uno de mis intentos salio rechazado, no se cual.",
            "Hubo un rechazo y no se que operacion lo tuvo.",
            "Algo me lo rechazaron, no se cual.",
        ],
    ),
    (
        "v2amb_es_08",
        "LEXICAL_OVERLAP",
        "es",
        [
            "No se si fue un pago pendiente o uno rechazado, hay varios.",
            "Puede ser el que quedo aprobado o el pendiente, no se cual.",
            "No distingo si el problema es en el aprobado o en el devuelto.",
            "Entre un movimiento pendiente y otro devuelto, no se cual.",
        ],
    ),
    (
        "v2amb_es_09",
        "COLLOQUIAL_OR_NOISY",
        "es",
        [
            "me paso algo con un pago pero no se cual de todos",
            "hay varias y no se cual me fallo",
            "me falta plata y no se de q movim",
            "un pago me fallo y no se cual es",
        ],
    ),
    (
        "v2amb_es_10",
        "COLLOQUIAL_OR_NOISY",
        "es",
        [
            "No se, algo con uno de mis pagos, pero ni idea cual.",
            "Alguno de mis movimientos salio mal, no se cual.",
            "Hubo un problema, pero no se que operacion.",
            "Me fallo uno, no se cual.",
        ],
    ),
    (
        "v2amb_es_11",
        "LOW_CONTEXT",
        "es",
        [
            "No se cual pago es.",
            "No identifico el movimiento.",
            "Hay varias, no se cual.",
            "No se que operacion fue.",
        ],
    ),
    (
        "v2amb_es_12",
        "LOW_CONTEXT",
        "es",
        [
            "No se cual de los dos.",
            "Alguna que otra, no se.",
            "No se el numero.",
            "No se cual fallo.",
        ],
    ),
    (
        "v2amb_es_13",
        "INDIRECT",
        "es",
        [
            "En mi historial hay algo que no me cierra y no se que es.",
            "Sospecho de un movimiento, pero no se cual.",
            "Algo entre mis operaciones no esta bien, no se cual.",
            "Me da la impresion de que un pago salio mal, no se cual.",
        ],
    ),
    (
        "v2amb_pt_14",
        "DIRECT",
        "pt",
        [
            "Tenho um problema com um pagamento mas nao sei qual de todos.",
            "Nao tenho certeza de qual dos meus movimentos foi o que falhou.",
            "Aconteceu algo com uma das minhas transferencias, nao sei qual.",
            "Tem varias operacoes e nao identifico a do problema.",
        ],
    ),
    (
        "v2amb_pt_15",
        "DIRECT",
        "pt",
        [
            "Pode ser o pagamento de ontem ou o de anteontem, nao sei qual.",
            "Tenho dois lancamentos parecidos e nao sei qual e o errado.",
            "Entre dois movimentos iguais nao sei qual teve o problema.",
            "Nao consigo distinguir qual dos dois pagamentos e.",
        ],
    ),
    (
        "v2amb_pt_16",
        "DIRECT",
        "pt",
        [
            "Tive um problema com uma operacao mas nao sei o numero.",
            "Algo deu errado com um pagamento, nao lembro qual.",
            "Um movimento deu problema e nao sei qual e.",
            "Surgiu um problema, nao sei qual operacao foi.",
        ],
    ),
    (
        "v2amb_pt_17",
        "INDIRECT",
        "pt",
        [
            "Alguma das minhas compras da semana nao bate, nao sei qual.",
            "Acho que me cobraram algo estranho, nao sei que movimento.",
            "Esta faltando dinheiro e nao sei de que operacao.",
            "Algo nao bate nos meus movimentos, nao sei qual.",
        ],
    ),
    (
        "v2amb_pt_18",
        "INDIRECT",
        "pt",
        [
            "Fiz varios envios seguidos e um nao bate, nao sei qual.",
            "Tenho dois saques no mesmo dia e nao sei qual falhou.",
            "Varios pagamentos iguais e um e o problematico, nao sei qual.",
            "Nao sei qual dos envios que fiz teve o problema.",
        ],
    ),
    (
        "v2amb_pt_19",
        "HARD_NEGATIVE",
        "pt",
        [
            "Tem algo pendente mas nao sei qual dos meus pagamentos e.",
            "Uma operacao ficou pendente e nao sei qual.",
            "Aparece algo pendente e nao identifico o movimento.",
            "Tenho um pendente, nao sei qual.",
        ],
    ),
    (
        "v2amb_pt_20",
        "HARD_NEGATIVE",
        "pt",
        [
            "Recusaram algo mas nao sei qual dos pagamentos.",
            "Uma das minhas tentativas deu recusado, nao sei qual.",
            "Houve uma recusa e nao sei que operacao foi.",
            "Algo foi recusado, nao sei qual.",
        ],
    ),
    (
        "v2amb_pt_21",
        "LEXICAL_OVERLAP",
        "pt",
        [
            "Nao sei se foi um pagamento pendente ou um recusado, tem varios.",
            "Pode ser o que ficou aprovado ou o pendente, nao sei qual.",
            "Nao distingo se o problema e no aprovado ou no devolvido.",
            "Entre um movimento pendente e outro devolvido, nao sei qual.",
        ],
    ),
    (
        "v2amb_pt_22",
        "COLLOQUIAL_OR_NOISY",
        "pt",
        [
            "aconteceu algo com um pagamento mas nao sei qual de todos",
            "tem varias e nao sei qual falhou",
            "ta faltando grana e nao sei de q movim",
            "um pagamento falhou e nao sei qual e",
        ],
    ),
    (
        "v2amb_pt_23",
        "COLLOQUIAL_OR_NOISY",
        "pt",
        [
            "Sei la, algo com um dos meus pagamentos, mas nem ideia qual.",
            "Algum dos meus movimentos deu ruim, nao sei qual.",
            "Deu um problema, mas nao sei que operacao.",
            "Falhou um, nao sei qual.",
        ],
    ),
    (
        "v2amb_pt_24",
        "LOW_CONTEXT",
        "pt",
        [
            "Nao sei qual pagamento e.",
            "Nao identifico o movimento.",
            "Tem varias, nao sei qual.",
            "Nao sei que operacao foi.",
        ],
    ),
    (
        "v2amb_pt_25",
        "LOW_CONTEXT",
        "pt",
        [
            "Nao sei qual dos dois.",
            "Alguma delas, nao sei.",
            "Nao sei o numero.",
            "Nao sei qual falhou.",
        ],
    ),
]

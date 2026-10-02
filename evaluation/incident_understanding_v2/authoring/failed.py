"""Independently authored Challenge Set v2 families for FAILED_OR_DECLINED."""

LABEL = "FAILED_OR_DECLINED"

FAMILIES = [
    (
        "v2fail_es_01",
        "DIRECT",
        "es",
        [
            "Intente pagar con la tarjeta y me la rechazo.",
            "El datofono no acepto mi tarjeta, salio rechazada.",
            "Mi compra no paso, me marco rechazado.",
            "Probe pagar y la operacion salio rechazada.",
        ],
    ),
    (
        "v2fail_es_02",
        "DIRECT",
        "es",
        [
            "No pude completar la transferencia, me la rechazo el sistema.",
            "Al enviar la plata me dijo que la operacion no se pudo realizar.",
            "La transferencia no se hizo, salio fallida.",
            "Intente transferir y quedo rechazada.",
        ],
    ),
    (
        "v2fail_es_03",
        "DIRECT",
        "es",
        [
            "El pago no se pudo procesar, me aparece fallido.",
            "Mi pago salio fallido y no se cobro.",
            "La operacion no paso, quedo como fallida.",
            "El cobro no se completo, fallo.",
        ],
    ),
    (
        "v2fail_es_04",
        "INDIRECT",
        "es",
        [
            "Quise mandar plata y no salio, se corto sola.",
            "Trate de pagar y no me dejo, no paso nada.",
            "Intente hacer el envio y no se concreto.",
            "Hice el intento de transferir y quedo en nada.",
        ],
    ),
    (
        "v2fail_es_05",
        "INDIRECT",
        "es",
        [
            "En la caja me dijeron que no se pudo cobrar.",
            "El comercio no logro cobrarme, no paso la operacion.",
            "No me aceptaron el pago en el local.",
            "La tienda no pudo procesar el cobro.",
        ],
    ),
    (
        "v2fail_es_06",
        "HARD_NEGATIVE",
        "es",
        [
            "Me anularon la operacion porque no se pudo concretar, nunca llego a hacerse.",
            "Cancelaron el intento y quedo como no realizada.",
            "La anularon antes de que pasara, no se completo.",
            "Me la cancelaron y nunca se ejecuto.",
        ],
    ),
    (
        "v2fail_es_07",
        "HARD_NEGATIVE",
        "es",
        [
            "Estuvo en proceso un rato y al final salio fallido.",
            "Pense que seguia pendiente pero termino en fallo.",
            "Quedo en proceso y luego me lo marcaron como rechazado.",
            "Lo vi pendiente y al final no paso, fallo.",
        ],
    ),
    (
        "v2fail_es_08",
        "LEXICAL_OVERLAP",
        "es",
        [
            "Primero me salio aprobado y despues rechazado, no se entiende.",
            "Marco aprobado un segundo y luego rechazado, nunca se hizo.",
            "Paso de aprobado a rechazado en el mismo momento.",
            "Me aparecio aprobado y enseguida rechazado, quedo sin hacer.",
        ],
    ),
    (
        "v2fail_es_09",
        "COLLOQUIAL_OR_NOISY",
        "es",
        [
            "no me dejo pagar la tarjeta, sale rechazada siempre",
            "intente transferir y nada, no paso",
            "el pago no agarra, ta fallando",
            "mi compra no pasa ni de casualidad",
        ],
    ),
    (
        "v2fail_es_10",
        "COLLOQUIAL_OR_NOISY",
        "es",
        [
            "No ma, el pago no paso y ya me frustre.",
            "Mi tarjeta no pasa en ningun lado, que rollo.",
            "Intente y nel, no se pudo.",
            "El pago trono, no lo agarro.",
        ],
    ),
    (
        "v2fail_es_11",
        "LOW_CONTEXT",
        "es",
        [
            "No paso el pago.",
            "Me la rechazaron.",
            "Salio fallido.",
            "No se pudo.",
        ],
    ),
    (
        "v2fail_es_12",
        "LOW_CONTEXT",
        "es",
        [
            "Rechazado.",
            "Operacion fallida.",
            "No se concreto.",
            "Pago no realizado.",
        ],
    ),
    (
        "v2fail_es_13",
        "INDIRECT",
        "es",
        [
            "Fui a pagar y la maquina no quiso, tuve que usar efectivo.",
            "No logre hacer el envio, se me trabo y no salio.",
            "La compra no se pudo cerrar, se quedo a medias.",
            "El retiro no se concreto, me lo negaron.",
        ],
    ),
    (
        "v2fail_pt_14",
        "DIRECT",
        "pt",
        [
            "Tentei pagar com o cartao e foi recusado.",
            "A maquininha nao aceitou meu cartao, deu recusado.",
            "Minha compra nao passou, apareceu recusada.",
            "Tentei pagar e a operacao foi recusada.",
        ],
    ),
    (
        "v2fail_pt_15",
        "DIRECT",
        "pt",
        [
            "Nao consegui completar a transferencia, o sistema recusou.",
            "Ao enviar o dinheiro disse que a operacao nao pode ser feita.",
            "A transferencia nao foi, deu falha.",
            "Tentei transferir e ficou recusada.",
        ],
    ),
    (
        "v2fail_pt_16",
        "DIRECT",
        "pt",
        [
            "O pagamento nao pode ser processado, aparece falhou.",
            "Meu pagamento deu falha e nao foi cobrado.",
            "A operacao nao passou, ficou como falha.",
            "A cobranca nao completou, deu erro.",
        ],
    ),
    (
        "v2fail_pt_17",
        "INDIRECT",
        "pt",
        [
            "Quis mandar dinheiro e nao foi, caiu sozinho.",
            "Tentei pagar e nao deixou, nao aconteceu nada.",
            "Tentei fazer o envio e nao se concretizou.",
            "Fiz a tentativa de transferir e deu em nada.",
        ],
    ),
    (
        "v2fail_pt_18",
        "INDIRECT",
        "pt",
        [
            "No caixa me disseram que nao deu pra cobrar.",
            "O comercio nao conseguiu me cobrar, a operacao nao passou.",
            "Nao aceitaram meu pagamento no local.",
            "A loja nao conseguiu processar a cobranca.",
        ],
    ),
    (
        "v2fail_pt_19",
        "HARD_NEGATIVE",
        "pt",
        [
            "Anularam a operacao porque nao deu pra concretizar, nunca chegou a acontecer.",
            "Cancelaram a tentativa e ficou como nao realizada.",
            "Anularam antes de acontecer, nao completou.",
            "Cancelaram e nunca foi executada.",
        ],
    ),
    (
        "v2fail_pt_20",
        "HARD_NEGATIVE",
        "pt",
        [
            "Ficou em processamento um tempo e no fim deu falha.",
            "Pensei que ainda estava pendente mas acabou em falha.",
            "Ficou processando e depois marcaram como recusado.",
            "Vi pendente e no final nao passou, falhou.",
        ],
    ),
    (
        "v2fail_pt_21",
        "LEXICAL_OVERLAP",
        "pt",
        [
            "Primeiro apareceu aprovado e depois recusado, nao da pra entender.",
            "Marcou aprovado por um segundo e logo recusado, nunca aconteceu.",
            "Passou de aprovado pra recusado na mesma hora.",
            "Apareceu aprovado e na hora recusado, ficou sem fazer.",
        ],
    ),
    (
        "v2fail_pt_22",
        "COLLOQUIAL_OR_NOISY",
        "pt",
        [
            "meu cartao nao passa em lugar nenhum, da recusado sempre",
            "tentei transferir e nada, nao foi",
            "o pagamento nao pega, ta falhando",
            "minha compra nao passa de jeito nenhum",
        ],
    ),
    (
        "v2fail_pt_23",
        "COLLOQUIAL_OR_NOISY",
        "pt",
        [
            "Oxe, o pagamento nao passou e ja fiquei bolado.",
            "Meu cartao nao passa em canto nenhum, que coisa.",
            "Tentei e nada, nao deu.",
            "O pagamento deu ruim, nao pegou.",
        ],
    ),
    (
        "v2fail_pt_24",
        "LOW_CONTEXT",
        "pt",
        [
            "O pagamento nao passou.",
            "Recusaram.",
            "Deu falha.",
            "Nao deu.",
        ],
    ),
    (
        "v2fail_pt_25",
        "LOW_CONTEXT",
        "pt",
        [
            "Recusado.",
            "Operacao falhou.",
            "Nao se concretizou.",
            "Pagamento nao realizado.",
        ],
    ),
]

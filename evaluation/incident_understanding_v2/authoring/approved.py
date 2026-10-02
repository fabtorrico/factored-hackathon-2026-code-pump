"""Independently authored Challenge Set v2 families for APPROVED_BUT_UNRESOLVED."""

LABEL = "APPROVED_BUT_UNRESOLVED"

FAMILIES = [
    (
        "v2appr_es_01",
        "DIRECT",
        "es",
        [
            "El banco me dice que la transferencia se completo, pero mi proveedor no la recibio.",
            "La operacion figura exitosa y el destinatario jura que no le llego.",
            "Me confirmaron que salio bien, pero alla no hay plata.",
            "Aparece realizada y la persona no la tiene.",
        ],
    ),
    (
        "v2appr_es_02",
        "DIRECT",
        "es",
        [
            "De mi lado salio todo bien, el problema es que no le entra al que recibe.",
            "Mi aplicacion dice completado, pero el otro no ve nada.",
            "El envio se dio por hecho y no lo han recibido.",
            "A mi me aparece listo y al receptor le falta.",
        ],
    ),
    (
        "v2appr_es_03",
        "INDIRECT",
        "es",
        [
            "Me descontaron y me dijeron que salio perfecto, pero el pedido no lo ven.",
            "Todo indica que se pago, sin embargo el comercio no lo tiene.",
            "Se supone que se hizo bien, pero no llego a ningun lado.",
            "Marco bien de mi lado y no llega al destino.",
        ],
    ),
    (
        "v2appr_es_04",
        "HARD_NEGATIVE",
        "es",
        [
            "Ya no esta pendiente, paso todo, el problema es que el receptor no la ve.",
            "Dejo de estar en proceso y quedo hecha, pero no le llega.",
            "No esta pendiente, esta completa, solo que no la reciben.",
            "Salio del proceso y quedo realizada, pero el otro lado no la tiene.",
        ],
    ),
    (
        "v2appr_es_05",
        "HARD_NEGATIVE",
        "es",
        [
            "Me la habian rechazado antes; ahora me la dieron por hecha y no le llega al destinatario.",  # noqa: E501
            "Ya no me sale rechazada, sino completada, pero no la reciben.",
            "En intentos previos fallo, este paso y no llega.",
            "Antes se rechazo, esta salio bien y aun asi no llega.",
        ],
    ),
    (
        "v2appr_es_06",
        "LEXICAL_OVERLAP",
        "es",
        [
            "Figura aprobada, el proceso cerro, pero el receptor no la tiene.",
            "Quedo aprobada y completada, lo que pasa es que no llega.",
            "Aprobada y sin embargo el destinatario no la ve.",
            "Esta aprobada y cerrada, pero no se acredito alla.",
        ],
    ),
    (
        "v2appr_es_07",
        "LEXICAL_OVERLAP",
        "es",
        [
            "Ya no esta en curso, termino, pero el dinero no aparece al otro lado.",
            "No sigue en proceso, finalizo, y el receptor no la tiene.",
            "Dejo de estar en curso, salio bien, pero no llega.",
            "Termino el proceso, figura exitosa, y no la reciben.",
        ],
    ),
    (
        "v2appr_es_08",
        "COLLOQUIAL_OR_NOISY",
        "es",
        [
            "la app dice q todo salio bien pero mi proveedor no ve la plata",
            "me aparece completado y el otro no tiene nada",
            "se supone q se envio bien y no llega",
            "todo salio ok de mi lado pero alla no cae",
        ],
    ),
    (
        "v2appr_es_09",
        "COLLOQUIAL_OR_NOISY",
        "es",
        [
            "O sea, todo perfecto de mi lado, pero al final no le llego a nadie.",
            "Mi banco dice que si, la persona dice que no.",
            "Me lo dieron por hecho y el otro ni lo vio.",
            "Sali bien en la app, pero no llego.",
        ],
    ),
    (
        "v2appr_es_10",
        "LOW_CONTEXT",
        "es",
        [
            "Dice completado pero no llego.",
            "Figura hecha y no la reciben.",
            "Salio bien, pero no entra.",
            "Exitoso de mi lado, sin llegar.",
        ],
    ),
    (
        "v2appr_es_11",
        "LOW_CONTEXT",
        "es",
        [
            "Aprobada, pero el otro no la ve.",
            "Hecha y no llega.",
            "Cerrada, sin acreditar alla.",
            "OK de mi lado, falta alla.",
        ],
    ),
    (
        "v2appr_es_12",
        "INDIRECT",
        "es",
        [
            "El comprobante dice que se hizo, pero el negocio no lo registra.",
            "Me llego el aviso de exito y al receptor no le entra.",
            "Segun el banco quedo lista, y el proveedor no la tiene.",
            "El recibo dice hecho y alla no aparece.",
        ],
    ),
    (
        "v2appr_es_13",
        "HARD_NEGATIVE",
        "es",
        [
            "No es que este lenta, ya termino, el detalle es que no le llega al receptor.",
            "No esta demorando, se hizo, pero el otro no la ve.",
            "Ya paso, no sigue en proceso, solo que no se acredita alla.",
            "No se esta tardando, concluyo, pero no llega.",
        ],
    ),
    (
        "v2appr_pt_14",
        "DIRECT",
        "pt",
        [
            "O banco diz que a transferencia foi concluida, mas o meu fornecedor nao recebeu.",
            "A operacao aparece como bem-sucedida e o destinatario jura que nao chegou.",
            "Confirmaram que deu certo, mas la nao tem o dinheiro.",
            "Aparece realizada e a pessoa nao tem.",
        ],
    ),
    (
        "v2appr_pt_15",
        "DIRECT",
        "pt",
        [
            "Do meu lado deu tudo certo, o problema e que nao entra pra quem recebe.",
            "Meu aplicativo diz concluido, mas o outro nao ve nada.",
            "O envio foi dado como feito e nao receberam.",
            "Pra mim aparece pronto e pro destinatario falta.",
        ],
    ),
    (
        "v2appr_pt_16",
        "INDIRECT",
        "pt",
        [
            "Me descontaram e disseram que deu tudo certo, mas o pedido nao aparece.",
            "Tudo indica que foi pago, porem o comercio nao tem.",
            "Era pra ter sido feito direito, mas nao chegou a lugar nenhum.",
            "Deu certo do meu lado e nao chega no destino.",
        ],
    ),
    (
        "v2appr_pt_17",
        "HARD_NEGATIVE",
        "pt",
        [
            "Nao esta mais pendente, passou tudo, o problema e que o destinatario nao ve.",
            "Saiu do processamento e ficou feita, mas nao chega.",
            "Nao esta pendente, esta completa, so que nao recebem.",
            "Saiu do processo e ficou realizada, mas do outro lado nao tem.",
        ],
    ),
    (
        "v2appr_pt_18",
        "HARD_NEGATIVE",
        "pt",
        [
            "Ja tinham recusado antes; agora deram como feita e nao chega pro destinatario.",
            "Nao aparece mais recusada, e sim concluida, mas nao recebem.",
            "Em tentativas anteriores falhou, essa passou e nao chega.",
            "Antes foi recusada, essa deu certo e mesmo assim nao chega.",
        ],
    ),
    (
        "v2appr_pt_19",
        "LEXICAL_OVERLAP",
        "pt",
        [
            "Aparece aprovada, o processo fechou, mas o destinatario nao tem.",
            "Ficou aprovada e concluida, o que acontece e que nao chega.",
            "Aprovada e mesmo assim o destinatario nao ve.",
            "Esta aprovada e encerrada, mas nao caiu la.",
        ],
    ),
    (
        "v2appr_pt_20",
        "LEXICAL_OVERLAP",
        "pt",
        [
            "Nao esta mais em andamento, terminou, mas o dinheiro nao aparece do outro lado.",
            "Nao continua em processo, finalizou, e o destinatario nao tem.",
            "Saiu do andamento, deu certo, mas nao chega.",
            "Terminou o processo, aparece bem-sucedida, e nao recebem.",
        ],
    ),
    (
        "v2appr_pt_21",
        "COLLOQUIAL_OR_NOISY",
        "pt",
        [
            "o app diz q deu tudo certo mas meu fornecedor nao ve a grana",
            "me aparece concluido e o outro nao tem nada",
            "supostamente foi enviado certo e nao chega",
            "deu tudo ok do meu lado mas nao cai la",
        ],
    ),
    (
        "v2appr_pt_22",
        "COLLOQUIAL_OR_NOISY",
        "pt",
        [
            "Tipo, tudo certo do meu lado, mas no fim nao chegou pra ninguem.",
            "Meu banco diz que sim, a pessoa diz que nao.",
            "Deram como feito e o outro nem viu.",
            "Deu certo no app, mas nao chegou.",
        ],
    ),
    (
        "v2appr_pt_23",
        "LOW_CONTEXT",
        "pt",
        [
            "Diz concluido mas nao chegou.",
            "Aparece feito e nao recebem.",
            "Deu certo, mas nao entra.",
            "OK do meu lado, sem chegar.",
        ],
    ),
    (
        "v2appr_pt_24",
        "LOW_CONTEXT",
        "pt",
        [
            "Aprovada, mas o outro nao ve.",
            "Feita e nao chega.",
            "Encerrada, sem creditar la.",
            "OK daqui, falta la.",
        ],
    ),
    (
        "v2appr_pt_25",
        "INDIRECT",
        "pt",
        [
            "O comprovante diz que foi feito, mas o negocio nao registra.",
            "Recebi o aviso de sucesso e pro destinatario nao entra.",
            "Segundo o banco ficou pronta, e o fornecedor nao tem.",
            "O recibo diz feito e la nao aparece.",
        ],
    ),
]

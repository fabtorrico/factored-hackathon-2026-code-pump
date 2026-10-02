"""Independently authored Challenge Set v2 families for PENDING_OR_DELAYED.

Format: (family_id, tier, language, [variant, ...]). Every family is single-language;
ES and PT families are authored separately and are not translation pairs.
"""

LABEL = "PENDING_OR_DELAYED"

FAMILIES = [
    (
        "v2pend_es_01",
        "DIRECT",
        "es",
        [
            "Hice una transferencia esta manana y todavia no aparece en la cuenta del destinatario.",  # noqa: E501
            "Envie plata a mi mama hace unas horas y a ella no le ha entrado nada.",
            "El dinero ya salio pero en la cuenta de destino no figura todavia.",
            "Mi envio esta hecho desde el mediodia y sigue sin reflejarse.",
        ],
    ),
    (
        "v2pend_es_02",
        "DIRECT",
        "es",
        [
            "Pague en la tienda y el sistema dice que la operacion aun se esta procesando.",
            "El pago de la compra quedo en proceso y no se ha confirmado.",
            "Mete el pago y sigue procesandose, ya van dos horas.",
            "La compra la pague pero aparece como en curso.",
        ],
    ),
    (
        "v2pend_es_03",
        "DIRECT",
        "es",
        [
            "Deposite en efectivo y el saldo aun no lo muestra.",
            "El deposito que hice hoy no se ve reflejado en la aplicacion.",
            "Consigne plata y todavia no me aparece el abono.",
            "Hice una consignacion y el monto sigue sin acreditarse.",
        ],
    ),
    (
        "v2pend_es_04",
        "INDIRECT",
        "es",
        [
            "A mi me descontaron la plata de la cuenta pero a mi hermano no le llego.",
            "Veo el cargo en mi cuenta y al otro lado no hay nada.",
            "Me sacaron el monto y el receptor sigue esperando.",
            "La plata salio de aca y alla no entra.",
        ],
    ),
    (
        "v2pend_es_05",
        "INDIRECT",
        "es",
        [
            "Estoy esperando una transferencia que me mandaron ayer y nada.",
            "Me dijeron que me transferian y hasta ahora no veo el dinero.",
            "Tendria que haberme llegado un pago y no aparece.",
            "Espero un abono que se demora y no baja.",
        ],
    ),
    (
        "v2pend_es_06",
        "HARD_NEGATIVE",
        "es",
        [
            "El sistema marco la operacion como aprobada, pero sigue en proceso y no ha salido.",
            "Dice aprobada pero la veo trabada en proceso.",
            "Me aparece aprobada hace rato y sin embargo no avanza.",
            "La dejaron como aprobada y todavia sigue en curso.",
        ],
    ),
    (
        "v2pend_es_07",
        "HARD_NEGATIVE",
        "es",
        [
            "La semana pasada me reversaron una operacion por error, ahora esta nueva lleva horas sin completarse.",  # noqa: E501
            "Me devolvieron una vez un pago, esta vez el problema es que el mio sigue en proceso.",
            "Ya me paso que anularon una, ahora simplemente no termina de procesarse.",
            "En otra ocasion me revirtieron, hoy lo que pasa es que la operacion no concluye.",
        ],
    ),
    (
        "v2pend_es_08",
        "LEXICAL_OVERLAP",
        "es",
        [
            "El pago esta aprobado pero la transferencia sigue pendiente y no se completa.",
            "Tengo un movimiento aprobado que quedo pendiente de procesar.",
            "Figura aprobado y pendiente a la vez, y no termina.",
            "Me sale aprobado en un lado y pendiente en el otro, sin completarse.",
        ],
    ),
    (
        "v2pend_es_09",
        "COLLOQUIAL_OR_NOISY",
        "es",
        [
            "ya pasaron como 5 horas y mi tranferencia no llega todavia",
            "hise un pago y aun no se refleja nada",
            "mande plata y no aparece x ningun lado",
            "mi envio ta en proceso hace rato y nada",
        ],
    ),
    (
        "v2pend_es_10",
        "COLLOQUIAL_OR_NOISY",
        "es",
        [
            "Oye, mande una plata y nada que llega, que paso?",
            "Neta que mi transferencia no cae, ya me preocupe.",
            "Mi pago sigue colgado y no se mueve.",
            "Mi transfer no ha caido, me ayudas?",
        ],
    ),
    (
        "v2pend_es_11",
        "LOW_CONTEXT",
        "es",
        [
            "Sigue en proceso.",
            "Aun no llega.",
            "Todavia no baja el pago.",
            "No se completo aun.",
        ],
    ),
    (
        "v2pend_es_12",
        "LOW_CONTEXT",
        "es",
        [
            "Pago en curso.",
            "Transferencia sin llegar.",
            "El monto no cae.",
            "Continua pendiente el envio.",
        ],
    ),
    (
        "v2pend_es_13",
        "INDIRECT",
        "es",
        [
            "Hice el envio anoche y hoy el beneficiario no tiene el dinero.",
            "Mi pago de ayer todavia no impacta en la otra cuenta.",
            "Desde ayer nadie ve el dinero que mande.",
            "La operacion de anoche sigue sin llegar a destino.",
        ],
    ),
    (
        "v2pend_pt_14",
        "DIRECT",
        "pt",
        [
            "Fiz uma transferencia de manha e ainda nao caiu na conta de quem recebe.",
            "Mandei dinheiro pra minha irma e ate agora nada.",
            "O valor saiu da minha conta mas nao entrou na do destinatario.",
            "Minha transferencia esta desde cedo sem aparecer.",
        ],
    ),
    (
        "v2pend_pt_15",
        "DIRECT",
        "pt",
        [
            "Paguei na loja e a operacao continua em processamento.",
            "O pagamento ficou em andamento e nao confirmou.",
            "Fiz o pagamento e ainda esta sendo processado.",
            "A compra aparece como em curso ate agora.",
        ],
    ),
    (
        "v2pend_pt_16",
        "DIRECT",
        "pt",
        [
            "Depositei em dinheiro e o saldo nao atualizou.",
            "Fiz um deposito hoje e ainda nao caiu na conta.",
            "O valor que depositei nao aparece no aplicativo.",
            "Depositei e o credito nao entrou.",
        ],
    ),
    (
        "v2pend_pt_17",
        "INDIRECT",
        "pt",
        [
            "Descontaram o dinheiro de mim mas meu primo nao recebeu.",
            "Vejo a cobranca na minha conta e do outro lado nada.",
            "Tiraram o valor daqui e quem recebe esta esperando.",
            "O dinheiro saiu daqui e nao chegou la.",
        ],
    ),
    (
        "v2pend_pt_18",
        "INDIRECT",
        "pt",
        [
            "Estou esperando uma transferencia que me enviaram ontem e nada.",
            "Disseram que iam me transferir e ate agora nao vi o dinheiro.",
            "Era pra ter caido um pagamento e nao aparece.",
            "Espero um valor que esta demorando e nao entra.",
        ],
    ),
    (
        "v2pend_pt_19",
        "HARD_NEGATIVE",
        "pt",
        [
            "O sistema marcou como aprovado mas continua em processamento e nao saiu.",
            "Aparece aprovado e mesmo assim segue travado.",
            "Ficou aprovado faz tempo e nao avanca.",
            "Marcaram como aprovado e ainda esta em andamento.",
        ],
    ),
    (
        "v2pend_pt_20",
        "HARD_NEGATIVE",
        "pt",
        [
            "Semana passada reverteram uma operacao por engano, agora essa nova esta horas sem concluir.",  # noqa: E501
            "Ja me devolveram um pagamento uma vez, hoje o problema e que o meu nao termina de processar.",  # noqa: E501
            "Ja anularam uma antes, agora so nao conclui.",
            "Outra vez foi revertida, hoje e que nao finaliza.",
        ],
    ),
    (
        "v2pend_pt_21",
        "LEXICAL_OVERLAP",
        "pt",
        [
            "O pagamento esta aprovado mas a transferencia segue pendente e nao completa.",
            "Tenho um lancamento aprovado que ficou pendente de processar.",
            "Aparece aprovado e pendente ao mesmo tempo, e nao termina.",
            "Mostra aprovado de um lado e pendente do outro, sem completar.",
        ],
    ),
    (
        "v2pend_pt_22",
        "COLLOQUIAL_OR_NOISY",
        "pt",
        [
            "ja faz umas 5 horas e minha transferencia nao chega ate agora",
            "fiz um pagamento e ainda nao cai nada",
            "mandei grana e nao aparece em lugar nenhum",
            "meu envio ta processando faz tempo e nada",
        ],
    ),
    (
        "v2pend_pt_23",
        "COLLOQUIAL_OR_NOISY",
        "pt",
        [
            "Cara, mandei um dinheiro e nao cai de jeito nenhum, que isso?",
            "A transferencia nao caiu ainda, ja to preocupado.",
            "O pagamento ta pendurado, me ajuda?",
            "Meu envio nao caiu, e agora?",
        ],
    ),
    (
        "v2pend_pt_24",
        "LOW_CONTEXT",
        "pt",
        [
            "Ainda esta processando.",
            "Nao caiu ainda.",
            "O valor nao entrou.",
            "Segue sem completar.",
        ],
    ),
    (
        "v2pend_pt_25",
        "LOW_CONTEXT",
        "pt",
        [
            "Transferencia em andamento.",
            "Sem chegar o pagamento.",
            "O dinheiro nao cai.",
            "Continua sem cair o envio.",
        ],
    ),
]

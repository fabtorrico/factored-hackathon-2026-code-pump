"""Independently authored Challenge Set v2 families for OUT_OF_SCOPE.

OUT_OF_SCOPE = the message is not a transaction/payment incident at all (app
usability, onboarding, account access, product questions, general complaints).
"""

LABEL = "OUT_OF_SCOPE"

FAMILIES = [
    (
        "v2oos_es_01",
        "DIRECT",
        "es",
        [
            "Quiero cambiar el color de la aplicacion a modo oscuro.",
            "Como activo las notificaciones en el celular nuevo?",
            "Donde puedo ver mis datos personales en la app?",
            "Necesito actualizar mi direccion de correo.",
        ],
    ),
    (
        "v2oos_es_02",
        "DIRECT",
        "es",
        [
            "La aplicacion se cierra sola cuando abro la camara.",
            "No me deja iniciar sesion, dice error de red.",
            "La pantalla se queda cargando y no avanza.",
            "El boton de mi perfil no responde.",
        ],
    ),
    (
        "v2oos_es_03",
        "INDIRECT",
        "es",
        [
            "Quiero saber que documentos necesito para abrir otro producto.",
            "Me interesa conocer los requisitos para una cuenta nueva.",
            "Tienen alguna guia para usar la herramienta de presupuesto?",
            "Donde veo las preguntas frecuentes?",
        ],
    ),
    (
        "v2oos_es_04",
        "HARD_NEGATIVE",
        "es",
        [
            "Olvide mi contrasena y no puedo entrar, no es un problema de un pago.",
            "Me bloquearon el acceso por intentos fallidos, es de la cuenta, no de una compra.",
            "No puedo ingresar y quiero recuperar mi usuario, nada de pagos.",
            "Perdi el acceso a mi cuenta, no tiene que ver con una operacion.",
        ],
    ),
    (
        "v2oos_es_05",
        "HARD_NEGATIVE",
        "es",
        [
            "Quiero pedir la baja de mi cuenta, no es por un movimiento.",
            "Necesito eliminar mis datos, no es un tema de pagos.",
            "Quiero cancelar mi suscripcion de la app, no una compra.",
            "Solicito dar de baja mi usuario, no es una operacion.",
        ],
    ),
    (
        "v2oos_es_06",
        "LEXICAL_OVERLAP",
        "es",
        [
            "En el historial no me sale un boton para descargar, es de la interfaz.",
            "En la lista de movimientos la app se ve mal, tema de pantalla.",
            "No encuentro el filtro del listado, es de la app.",
            "La seccion de operaciones tarda en abrir, es el sistema.",
        ],
    ),
    (
        "v2oos_es_07",
        "LEXICAL_OVERLAP",
        "es",
        [
            "Quiero una explicacion de como se calcula la comision, es una consulta.",
            "Necesito saber el horario de atencion de una sucursal.",
            "Consulta: aceptan un tipo de documento nuevo?",
            "Queria saber si tienen planes para jovenes.",
        ],
    ),
    (
        "v2oos_es_08",
        "COLLOQUIAL_OR_NOISY",
        "es",
        [
            "la app se cierra sola, se bugea todo",
            "no me deja entrar, me sale error de red",
            "la pantalla se queda cargando infinito",
            "el boton de perfil no hace nada",
        ],
    ),
    (
        "v2oos_es_09",
        "COLLOQUIAL_OR_NOISY",
        "es",
        [
            "Hola, buena tarde, solo queria preguntar por los horarios.",
            "Buenos dias, una consulta general nada mas.",
            "Disculpen la molestia, queria informacion.",
            "Hola, todo bien? queria saber si estan abiertos.",
        ],
    ),
    (
        "v2oos_es_10",
        "LOW_CONTEXT",
        "es",
        [
            "Quiero cambiar el modo oscuro.",
            "No me deja entrar.",
            "Es una consulta de horarios.",
            "Necesito informacion general.",
        ],
    ),
    (
        "v2oos_es_11",
        "LOW_CONTEXT",
        "es",
        [
            "Error de contrasena.",
            "Consulta de planes.",
            "La app se traba.",
            "Pregunta de documentos.",
        ],
    ),
    (
        "v2oos_es_12",
        "INDIRECT",
        "es",
        [
            "Como hago para que la app no gaste tantos datos?",
            "Hay forma de activar el ingreso con huella?",
            "Se puede personalizar la pantalla de inicio?",
            "Puedo recibir avisos por correo en vez de por la app?",
        ],
    ),
    (
        "v2oos_es_13",
        "HARD_NEGATIVE",
        "es",
        [
            "No es que un movimiento este mal, simplemente quiero saber como funciona el interes.",
            "No tengo un problema de pago, solo quiero entender la tabla de comisiones.",
            "No es un error de una compra, es una duda sobre el producto.",
            "No reclamo una operacion, quiero informacion sobre los planes.",
        ],
    ),
    (
        "v2oos_pt_14",
        "DIRECT",
        "pt",
        [
            "Quero mudar a cor do aplicativo para o modo escuro.",
            "Como ativo as notificacoes no celular novo?",
            "Onde consigo ver meus dados pessoais no app?",
            "Preciso atualizar meu endereco de e-mail.",
        ],
    ),
    (
        "v2oos_pt_15",
        "DIRECT",
        "pt",
        [
            "O aplicativo fecha sozinho quando abro a camera.",
            "Nao deixa eu entrar, diz erro de rede.",
            "A tela fica carregando e nao avanca.",
            "O botao do meu perfil nao responde.",
        ],
    ),
    (
        "v2oos_pt_16",
        "INDIRECT",
        "pt",
        [
            "Quero saber quais documentos preciso para abrir outro produto.",
            "Tenho interesse em conhecer os requisitos para uma conta nova.",
            "Tem algum guia para usar a ferramenta de orcamento?",
            "Onde vejo as perguntas frequentes?",
        ],
    ),
    (
        "v2oos_pt_17",
        "HARD_NEGATIVE",
        "pt",
        [
            "Esqueci minha senha e nao consigo entrar, nao e problema de um pagamento.",
            "Bloquearam meu acesso por tentativas erradas, e da conta, nao de uma compra.",
            "Nao consigo entrar e quero recuperar meu usuario, nada de pagamentos.",
            "Perdi o acesso a minha conta, nao tem a ver com uma operacao.",
        ],
    ),
    (
        "v2oos_pt_18",
        "HARD_NEGATIVE",
        "pt",
        [
            "Quero pedir o encerramento da minha conta, nao e por um movimento.",
            "Preciso excluir meus dados, nao e assunto de pagamentos.",
            "Quero cancelar a assinatura do app, nao uma compra.",
            "Solicito dar baixa no meu usuario, nao e uma operacao.",
        ],
    ),
    (
        "v2oos_pt_19",
        "LEXICAL_OVERLAP",
        "pt",
        [
            "No historico nao aparece um botao para baixar, e da interface.",
            "Na lista de movimentos o app fica estranho, questao de tela.",
            "Nao acho o filtro da listagem, e do app.",
            "A secao de operacoes demora a abrir, e do sistema.",
        ],
    ),
    (
        "v2oos_pt_20",
        "LEXICAL_OVERLAP",
        "pt",
        [
            "Quero uma explicacao de como a taxa e calculada, e uma consulta.",
            "Preciso saber o horario de atendimento de uma agencia.",
            "Consulta: aceitam um tipo de documento novo?",
            "Queria saber se tem planos para jovens.",
        ],
    ),
    (
        "v2oos_pt_21",
        "COLLOQUIAL_OR_NOISY",
        "pt",
        [
            "o app fecha sozinho, da bug em tudo",
            "nao deixa eu entrar, da erro de rede",
            "a tela fica carregando sem parar",
            "o botao de perfil nao faz nada",
        ],
    ),
    (
        "v2oos_pt_22",
        "COLLOQUIAL_OR_NOISY",
        "pt",
        [
            "Oi, boa tarde, so queria perguntar pelos horarios.",
            "Bom dia, uma consulta geral mesmo.",
            "Desculpa o incomodo, queria uma informacao.",
            "Oi, tudo bem? queria saber se estao abertos.",
        ],
    ),
    (
        "v2oos_pt_23",
        "LOW_CONTEXT",
        "pt",
        [
            "Quero mudar o modo escuro.",
            "Nao deixa eu entrar.",
            "E uma consulta de horarios.",
            "Preciso de informacao geral.",
        ],
    ),
    (
        "v2oos_pt_24",
        "LOW_CONTEXT",
        "pt",
        [
            "Erro de senha.",
            "Consulta de planos.",
            "O app trava.",
            "Pergunta de documentos.",
        ],
    ),
    (
        "v2oos_pt_25",
        "INDIRECT",
        "pt",
        [
            "Como faco pro app nao gastar tantos dados?",
            "Tem como ativar o acesso por digital?",
            "Da pra personalizar a tela inicial?",
            "Posso receber avisos por e-mail em vez do app?",
        ],
    ),
]

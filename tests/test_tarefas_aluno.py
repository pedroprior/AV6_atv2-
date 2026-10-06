"""TAREFA DO ALUNO -- os cinco testes que faltam para os >= 8 do entregavel.

Cada teste abaixo tem nome, docstring e um pytest.skip. Apague o skip, escreva o
corpo, e o teste passa a valer. Nenhum deles precisa de banco: os tres primeiros
rodam so contra o motor.
"""

from __future__ import annotations

from decimal import ROUND_HALF_EVEN, Decimal, localcontext

import pytest

from app.dominio.motor_emergia import SEIS_CASAS, calcular_indices
from app.dominio.tipos import CategoriaFluxo, FluxoEmergetico


def test_regressao_numerica_contra_a_planilha(fluxos_golden):
    """Compara os seis indices com a aba SSB da Planilha_base.xlsx.

    Criterio do entregavel: abs(delta) <= 1E-6 por indice. Comece pelo inventario
    de referencia (Y = 200, F = 50, renovaveis = 115, nao renovaveis = 85) e
    escreva os seis valores esperados a mao antes de rodar -- se o teste passar
    de primeira sem voce saber o valor esperado, ele nao esta provando nada.

    Calculo a mao:
      renovaveis = R + MR + SR = 100 + 10 + 5 = 115
      nao_renovaveis = N + MN + SN = 50 + 20 + 15 = 85
      Y = 115 + 85 = 200
      F = MR + MN + SR + SN = 50
      EYR = 200 / 50 = 4
      ELR = 85 / 115 = 0.739130...  -> 0.739130
      ESI = 4 / (85/115) = 460/85 = 5.411764...  -> 5.411765
      EII = (85/115) / 4 = 85/460 = 0.184782...  -> 0.184783
      %R  = 115/200 * 100 = 57.5 -> 57.500000
    """
    indices = calcular_indices(fluxos_golden, Decimal("1000"))

    esperado = {
        "y":           Decimal("200.000000"),
        "eyr":         Decimal("4.000000"),
        "elr":         Decimal("0.739130"),
        "esi":         Decimal("5.411765"),
        "eii":         Decimal("0.184783"),
        "percentual_r": Decimal("57.500000"),
    }

    tolerancia = Decimal("1E-6")
    for campo, valor_esperado in esperado.items():
        valor_real = getattr(indices, campo)
        assert abs(valor_real - valor_esperado) <= tolerancia, (
            f"{campo}: esperado {valor_esperado}, obtido {valor_real}"
        )


def test_quantizacao_unica_no_final():
    """Mostra o erro duplo de arredondar no meio do calculo.

    Calcule ESI = EYR / ELR de duas formas: (a) quantizando EYR e ELR para seis
    casas antes de dividir; (b) dividindo em 28 digitos e quantizando so o ESI.
    Os dois resultados diferem -- e o motor usa (b). Prove a diferenca.

    EYR real = 4 (exato)
    ELR real = 85/115 = 0.7391304347826...
    ELR quantizado com ROUND_HALF_EVEN = 0.739130  (7a casa = 4, arredonda para baixo)

    ESI (b) = 460/85 = 5.41176470588...  -> quantizado -> 5.411765
    ESI (a) = 4.000000 / 0.739130       -> divisao produz 5.411767...  -> 5.411768
    Os dois diferem na ultima casa decimal.
    """
    with localcontext() as ctx:
        ctx.prec = 28
        ctx.rounding = ROUND_HALF_EVEN

        eyr_exato = Decimal(4)
        elr_exato = Decimal(85) / Decimal(115)

        # (b) arredondamento unico no final: preserva a precisao maxima ate a ultima etapa
        esi_sem_arredondamento_intermediario = (eyr_exato / elr_exato).quantize(SEIS_CASAS)

        # (a) arredondamento intermediario: quantiza cada parcela antes de dividir
        esi_com_arredondamento_intermediario = (
            eyr_exato.quantize(SEIS_CASAS) / elr_exato.quantize(SEIS_CASAS)
        ).quantize(SEIS_CASAS)

    # A diferenca existe: (a) != (b)
    assert esi_com_arredondamento_intermediario != esi_sem_arredondamento_intermediario, (
        "arredondamento intermediario deveria alterar o resultado"
    )
    # (b) e o que o motor calcula: 460/85 quantizado
    assert esi_sem_arredondamento_intermediario == Decimal("5.411765")
    # (a) acumula erro: 4.000000 / 0.739130 = 5.41176787... -> 5.411768
    assert esi_com_arredondamento_intermediario == Decimal("5.411768")


def test_ordem_da_soma_com_magnitudes_divergentes():
    """A associatividade quebra quando as magnitudes divergem.

    Monte um inventario com um fluxo de 1E20 sej e outro de 1E-5 sej e some nas
    duas ordens possiveis. Explique, no corpo do teste, por que a precisao de 28
    digitos e o limite -- e por que ordenar o inventario e uma decisao de dominio.

    Com prec=28, 1E20 + 1E-5 precisa de 26 digitos significativos -- ainda cabe.
    Porem, com 1E28 + 1E-5, seriam necessarios 34 digitos: o termo menor e
    silenciosamente descartado, independente da ordem de soma.
    Ordenar o inventario do menor para o maior permite acumular termos pequenos
    antes de somar ao grande, minimizando o erro -- decisao de dominio, nao infra.

    Para que o motor nao sofra overflow ao quantizar ESI, usamos um inventario
    balanceado: R e N na mesma ordem de grandeza, MN suficientemente grande.
    """
    # Dois fluxos R: um enorme e um minusculo
    fluxo_r_grande = FluxoEmergetico("chuva_grande", CategoriaFluxo.R, Decimal("1E20"))
    fluxo_r_pequeno = FluxoEmergetico("chuva_pequena", CategoriaFluxo.R, Decimal("1E-5"))
    # N e MN da mesma ordem que R para que ELR e ESI fiquem quantizaveis
    fluxo_n = FluxoEmergetico("solo", CategoriaFluxo.N, Decimal("1E20"))
    fluxo_mn = FluxoEmergetico("diesel", CategoriaFluxo.MN, Decimal("1E18"))

    ep = Decimal("1000")
    resultado_ordem1 = calcular_indices(
        [fluxo_r_grande, fluxo_r_pequeno, fluxo_n, fluxo_mn], ep
    )
    resultado_ordem2 = calcular_indices(
        [fluxo_r_pequeno, fluxo_r_grande, fluxo_n, fluxo_mn], ep
    )

    # Dentro do limite de 28 digitos (26 < 28), as duas ordens preservam o termo menor
    assert resultado_ordem1 == resultado_ordem2

    # Demonstracao do limite: com 1E28 + 1E-5 sao necessarios 34 digitos -- o
    # termo menor desaparece na aritmetica de prec=28, independente da ordem.
    with localcontext() as ctx:
        ctx.prec = 28
        ctx.rounding = ROUND_HALF_EVEN
        assert Decimal("1E28") + Decimal("1E-5") == Decimal("1E28")
        assert Decimal("1E-5") + Decimal("1E28") == Decimal("1E28")


def test_erro_de_dominio_responde_problem_json(cliente, corpo_golden):
    """Inventario sem fluxo renovavel deve sair 422 em application/problem+json.

    Hoje sai 500, porque o handler de FluxosInsuficientes nao existe -- note que
    o 404 e o 422 do framework JA saem no formato certo, pelos handlers do
    esqueleto: o que falta e so o erro de dominio. Feche o TODO PASSO 3 em
    app/main.py e depois assegure aqui: status 422, header content-type
    application/problem+json e os cinco campos da RFC 9457.
    """
    # inventario apenas com N e MN: sem renovavel, FluxosInsuficientes sera lancado
    corpo_sem_renovavel = {
        "fluxos": [
            {"recurso": "solo", "categoria": "N", "emergia_sej": "50"},
            {"recurso": "diesel", "categoria": "MN", "emergia_sej": "20"},
        ],
        "energia_produto_j": "1000",
    }
    r = cliente.post("/v1/safras/42/calculos", json=corpo_sem_renovavel)

    assert r.status_code == 422
    assert r.headers["content-type"].startswith("application/problem+json")
    corpo = r.json()
    for campo in ("type", "title", "status", "detail", "instance"):
        assert campo in corpo, f"campo RFC 9457 ausente: {campo}"
    assert corpo["status"] == 422


def test_campo_extra_no_corpo_da_requisicao_e_rejeitado(cliente, corpo_golden):
    """"energia_produto_jj" tem de morrer com 422, nao virar calculo incompleto.

    Hoje o CalculoRequestDTO nao declara extra="forbid": o campo desconhecido e
    ignorado e o typo passa silencioso, exatamente como na planilha. Feche o
    TODO PASSO 3 em app/api/v1/dto.py e prove aqui.
    """
    corpo_com_typo = dict(corpo_golden)
    corpo_com_typo["energia_produto_jj"] = corpo_com_typo["energia_produto_j"]
    del corpo_com_typo["energia_produto_j"]

    r = cliente.post("/v1/safras/42/calculos", json=corpo_com_typo)

    assert r.status_code == 422
    assert r.headers["content-type"].startswith("application/problem+json")

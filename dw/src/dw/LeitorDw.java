package dw;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.*;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * Le arquivos .dw.
 *
 * A linguagem tem so 3 tipos de linha:
 *
 *   Todos os tanques:        -> abre o bloco que vale para todos
 *   Tanque 1                 -> abre o bloco do tanque 1 (":" opcional)
 *   VazaoMin: 200            -> define um limite no bloco atual
 *
 * Linhas em branco sao ignoradas. Tudo depois de # e comentario.
 * Maiusculas/minusculas e acentos nao importam.
 */
public final class LeitorDw {

    private static final Pattern TODOS =
            Pattern.compile("^todos\\s*(os)?\\s*(os\\s+)?tanques\\s*:?$");
    private static final Pattern TANQUE =
            Pattern.compile("^tanque\\s*(\\S+?)\\s*:?$");
    private static final Pattern ATRIBUICAO =
            Pattern.compile("^([^:=]+?)\\s*[:=]\\s*(.*)$");
    private static final Pattern NUMERO =
            Pattern.compile("^-?\\d+([.,]\\d+)?\\s*%?$");

    private static final int TODOS_OS_TANQUES = -1;

    private LeitorDw() {}

    public static Configuracao lerArquivo(Path arquivo) throws IOException, ErroDw {
        if (!arquivo.getFileName().toString().toLowerCase().endsWith(".dw")) {
            throw new ErroDw(List.of(new ErroDw.Problema(0,
                    "O arquivo precisa terminar com .dw (recebi: " + arquivo.getFileName() + ")")));
        }
        return ler(Files.readString(arquivo, StandardCharsets.UTF_8));
    }

    public static Configuracao ler(String conteudo) throws ErroDw {
        List<ErroDw.Problema> erros = new ArrayList<>();
        EnumMap<Parametro, Double> todos = new EnumMap<>(Parametro.class);
        Map<Integer, Map<Parametro, Double>> porTanque = new TreeMap<>();
        // onde cada valor foi definido: bloco -> parametro -> linha
        Map<Integer, Map<Parametro, Integer>> origem = new HashMap<>();

        Integer blocoAtual = null;
        int blocoAtualLinha = 0;
        boolean blocoAtualTemValor = true;
        String[] linhas = conteudo.replace("﻿", "").split("\\R", -1);

        for (int i = 0; i < linhas.length; i++) {
            int n = i + 1;
            String original = tirarComentario(linhas[i]).trim();
            if (original.isEmpty()) continue;
            String norm = normalizar(original);

            // --- "Todos os tanques:" ---
            if (TODOS.matcher(norm).matches()) {
                avisarBlocoVazio(blocoAtual, blocoAtualTemValor, blocoAtualLinha, erros);
                blocoAtual = TODOS_OS_TANQUES; blocoAtualLinha = n; blocoAtualTemValor = false;
                continue;
            }

            // --- "Tanque 1" ---
            Matcher mt = TANQUE.matcher(norm);
            if (mt.matches() && !norm.contains("=")) {
                String num = mt.group(1);
                if (!num.matches("\\d+") || Integer.parseInt(num) < 1) {
                    erros.add(new ErroDw.Problema(n, "\"" + original + "\": o numero do tanque precisa ser "
                            + "um numero inteiro a partir de 1. Ex.: Tanque 3"));
                    blocoAtual = null;
                    continue;
                }
                avisarBlocoVazio(blocoAtual, blocoAtualTemValor, blocoAtualLinha, erros);
                blocoAtual = Integer.parseInt(num); blocoAtualLinha = n; blocoAtualTemValor = false;
                porTanque.computeIfAbsent(blocoAtual, k -> new EnumMap<>(Parametro.class));
                continue;
            }

            // --- "VazaoMin: 200" ---
            Matcher ma = ATRIBUICAO.matcher(original);
            if (!ma.matches()) {
                erros.add(new ErroDw.Problema(n, "Nao entendi \"" + original + "\". Use \"Tanque 1\", "
                        + "\"Todos os tanques:\" ou \"NomeDoLimite: valor\" (ex.: VazaoMin: 200)"));
                continue;
            }
            blocoAtualTemValor = true; // ja tentou definir algo neste bloco
            String nomeParam = ma.group(1).trim();
            String textoValor = ma.group(2).trim();

            Parametro p = Parametro.porNome(nomeParam);
            if (p == null) {
                Parametro sugestao = Parametro.maisParecido(nomeParam);
                erros.add(new ErroDw.Problema(n, "\"" + nomeParam + "\" nao e um limite conhecido."
                        + (sugestao != null ? " Voce quis dizer \"" + sugestao.nome + "\"?"
                                            : " Limites validos: " + nomesValidos())));
                continue;
            }
            if (blocoAtual == null) {
                erros.add(new ErroDw.Problema(n, "\"" + p.nome + "\" esta fora de um bloco. Escreva antes "
                        + "\"Tanque 1\" (ou outro numero) ou \"Todos os tanques:\""));
                continue;
            }
            if (textoValor.isEmpty()) {
                erros.add(new ErroDw.Problema(n, "\"" + p.nome + "\" esta sem valor. Ex.: " + p.nome + ": 100"));
                continue;
            }
            if (!NUMERO.matcher(textoValor).matches()) {
                erros.add(new ErroDw.Problema(n, "O valor de \"" + p.nome + "\" precisa ser um numero "
                        + "(recebi \"" + textoValor + "\"). Ex.: " + p.nome + ": 100"));
                continue;
            }
            double valor = Double.parseDouble(textoValor.replace("%", "").trim().replace(',', '.'));
            if (valor < p.menorValorPermitido || valor > p.maiorValorPermitido) {
                erros.add(new ErroDw.Problema(n, "\"" + p.nome + ": " + textoValor + "\" esta fora do permitido "
                        + faixa(p)));
                continue;
            }

            Map<Parametro, Integer> linhasDoBloco = origem.computeIfAbsent(blocoAtual, k -> new EnumMap<>(Parametro.class));
            if (linhasDoBloco.containsKey(p)) {
                erros.add(new ErroDw.Problema(n, "\"" + p.nome + "\" ja foi definido para "
                        + nomeBloco(blocoAtual) + " na linha " + linhasDoBloco.get(p) + ". Deixe so um."));
                continue;
            }
            linhasDoBloco.put(p, n);
            if (blocoAtual == TODOS_OS_TANQUES) todos.put(p, valor);
            else porTanque.get(blocoAtual).put(p, valor);
        }
        avisarBlocoVazio(blocoAtual, blocoAtualTemValor, blocoAtualLinha, erros);

        Configuracao cfg = new Configuracao(todos, porTanque);
        if (erros.isEmpty()) validarMinMenorQueMax(cfg, erros);
        erros.sort(Comparator.comparingInt(e -> e.linha() == 0 ? Integer.MAX_VALUE : e.linha()));
        if (!erros.isEmpty()) throw new ErroDw(erros);
        return cfg;
    }

    /** Depois de juntar "Todos" + "Tanque N", o minimo nao pode passar do maximo. */
    private static void validarMinMenorQueMax(Configuracao cfg, List<ErroDw.Problema> erros) {
        Set<Integer> blocos = new LinkedHashSet<>();
        blocos.add(TODOS_OS_TANQUES);
        blocos.addAll(cfg.tanquesCitados());
        for (int b : blocos) {
            Map<Parametro, Double> l = b == TODOS_OS_TANQUES ? cfg.padraoTodos() : cfg.limitesDo(b);
            checar(l, Parametro.VAZAO_MIN, Parametro.VAZAO_MAX, b, erros);
            checar(l, Parametro.NIVEL_MIN, Parametro.NIVEL_MAX, b, erros);
        }
    }

    private static void checar(Map<Parametro, Double> l, Parametro min, Parametro max, int bloco,
                               List<ErroDw.Problema> erros) {
        Double a = l.get(min), b = l.get(max);
        if (a != null && b != null && a > b) {
            erros.add(new ErroDw.Problema(0, "Em " + nomeBloco(bloco) + ", " + min.nome + " ("
                    + Configuracao.formatar(a) + ") esta maior que " + max.nome + " ("
                    + Configuracao.formatar(b) + ")."));
        }
    }

    private static void avisarBlocoVazio(Integer bloco, boolean temValor, int linha, List<ErroDw.Problema> erros) {
        if (bloco != null && !temValor) {
            erros.add(new ErroDw.Problema(linha, nomeBloco(bloco) + " foi aberto mas nao tem nenhum limite "
                    + "embaixo. Ex.: VazaoMin: 200"));
        }
    }

    private static String tirarComentario(String linha) {
        int i = linha.indexOf('#');
        return i >= 0 ? linha.substring(0, i) : linha;
    }

    private static String normalizar(String s) {
        return java.text.Normalizer.normalize(s, java.text.Normalizer.Form.NFD)
                .replaceAll("\\p{M}", "").toLowerCase().replaceAll("\\s+", " ").trim();
    }

    private static String nomeBloco(int bloco) {
        return bloco == TODOS_OS_TANQUES ? "\"Todos os tanques\"" : "\"Tanque " + bloco + "\"";
    }

    private static String faixa(Parametro p) {
        String de = Configuracao.formatar(p.menorValorPermitido);
        return p.maiorValorPermitido == Double.MAX_VALUE ? "(precisa ser " + de + " ou mais)."
                : "(de " + de + " a " + Configuracao.formatar(p.maiorValorPermitido) + ").";
    }

    private static String nomesValidos() {
        StringJoiner j = new StringJoiner(", ");
        for (Parametro p : Parametro.values()) j.add(p.nome);
        return j.toString();
    }
}

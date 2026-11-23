package dw;

import java.text.Normalizer;

/**
 * Parametros que o PO pode alterar em um arquivo .dw.
 *
 * Para criar um parametro novo, basta adicionar uma linha aqui.
 * Ex.: TEMPERATURA_MAX("TemperaturaMax", -50, 150)
 */
public enum Parametro {

    VAZAO_MIN("VazaoMin", 0, Double.MAX_VALUE),
    VAZAO_MAX("VazaoMax", 0, Double.MAX_VALUE),
    NIVEL_MIN("NivelMin", 0, 100),
    NIVEL_MAX("NivelMax", 0, 100);

    /** Nome exatamente como o PO escreve no arquivo. */
    public final String nome;
    public final double menorValorPermitido;
    public final double maiorValorPermitido;

    Parametro(String nome, double menor, double maior) {
        this.nome = nome;
        this.menorValorPermitido = menor;
        this.maiorValorPermitido = maior;
    }

    /** Aceita "VazaoMin", "vazaomin", "Vazão Min", "VAZAO_MIN"... */
    public static Parametro porNome(String texto) {
        String alvo = normalizar(texto);
        for (Parametro p : values()) {
            if (normalizar(p.nome).equals(alvo)) return p;
        }
        return null;
    }

    /** Sugere o parametro mais parecido (para erros de digitacao). */
    public static Parametro maisParecido(String texto) {
        String alvo = normalizar(texto);
        Parametro melhor = null;
        int menorDistancia = Integer.MAX_VALUE;
        for (Parametro p : values()) {
            int d = distancia(alvo, normalizar(p.nome));
            if (d < menorDistancia) { menorDistancia = d; melhor = p; }
        }
        return menorDistancia <= 3 ? melhor : null;
    }

    static String normalizar(String s) {
        return Normalizer.normalize(s, Normalizer.Form.NFD)
                .replaceAll("\\p{M}", "")      // tira acentos
                .replaceAll("[\\s_\\-]", "")   // tira espacos, _ e -
                .toLowerCase();
    }

    private static int distancia(String a, String b) {
        int[] prev = new int[b.length() + 1];
        int[] cur = new int[b.length() + 1];
        for (int j = 0; j <= b.length(); j++) prev[j] = j;
        for (int i = 1; i <= a.length(); i++) {
            cur[0] = i;
            for (int j = 1; j <= b.length(); j++) {
                int custo = a.charAt(i - 1) == b.charAt(j - 1) ? 0 : 1;
                cur[j] = Math.min(Math.min(cur[j - 1] + 1, prev[j] + 1), prev[j - 1] + custo);
            }
            int[] t = prev; prev = cur; cur = t;
        }
        return prev[b.length()];
    }
}

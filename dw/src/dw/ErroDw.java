package dw;

import java.util.List;

/** Lancada quando o arquivo .dw tem problemas. Traz TODOS os erros de uma vez. */
public class ErroDw extends Exception {

    public record Problema(int linha, String mensagem) {
        @Override public String toString() {
            return linha > 0 ? "Linha " + linha + ": " + mensagem : mensagem;
        }
    }

    private final List<Problema> problemas;

    public ErroDw(List<Problema> problemas) {
        super(montarMensagem(problemas));
        this.problemas = List.copyOf(problemas);
    }

    public List<Problema> problemas() { return problemas; }

    private static String montarMensagem(List<Problema> problemas) {
        StringBuilder sb = new StringBuilder();
        sb.append(problemas.size() == 1 ? "Encontrei 1 problema no arquivo:\n"
                                        : "Encontrei " + problemas.size() + " problemas no arquivo:\n");
        for (Problema p : problemas) sb.append("  - ").append(p).append('\n');
        return sb.toString();
    }
}

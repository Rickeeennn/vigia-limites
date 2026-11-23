package dw;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Map;

/**
 * Linha de comando:
 *
 *   java -jar dw.jar tanques.dw            -> confere o arquivo e mostra o resultado
 *   java -jar dw.jar tanques.dw --json     -> mostra o resultado em JSON
 */
public class Main {

    public static void main(String[] args) {
        if (args.length == 0) {
            System.out.println("Uso: java -jar dw.jar <arquivo.dw> [--json]");
            System.exit(2);
        }
        Path arquivo = Path.of(args[0]);
        boolean json = args.length > 1 && args[1].equalsIgnoreCase("--json");

        if (!Files.exists(arquivo)) {
            System.err.println("Arquivo nao encontrado: " + arquivo);
            System.exit(2);
        }
        try {
            Configuracao cfg = LeitorDw.lerArquivo(arquivo);
            if (json) {
                System.out.println(cfg.paraJson());
            } else {
                System.out.println("OK! O arquivo " + arquivo.getFileName() + " esta correto.\n");
                if (!cfg.padraoTodos().isEmpty()) {
                    System.out.println("Todos os tanques: " + texto(cfg.padraoTodos()));
                }
                for (int t : cfg.tanquesCitados()) {
                    System.out.println("Tanque " + t + ": " + texto(cfg.limitesDo(t)));
                }
            }
        } catch (ErroDw e) {
            System.err.println(e.getMessage());
            System.exit(1);
        } catch (Exception e) {
            System.err.println("Nao consegui ler o arquivo: " + e.getMessage());
            System.exit(2);
        }
    }

    private static String texto(Map<Parametro, Double> m) {
        StringBuilder sb = new StringBuilder();
        m.forEach((p, v) -> sb.append(p.nome).append("=").append(Configuracao.formatar(v)).append("  "));
        return sb.toString().trim();
    }
}

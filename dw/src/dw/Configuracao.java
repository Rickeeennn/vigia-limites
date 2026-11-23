package dw;

import java.util.*;

/**
 * Resultado da leitura de um arquivo .dw.
 *
 * Regra: o valor definido em "Tanque N" vence o valor de "Todos os tanques".
 */
public class Configuracao {

    private final Map<Parametro, Double> todos;
    private final Map<Integer, Map<Parametro, Double>> porTanque;

    Configuracao(EnumMap<Parametro, Double> todos, Map<Integer, Map<Parametro, Double>> porTanque) {
        this.todos = Collections.unmodifiableMap(new EnumMap<>(todos));
        TreeMap<Integer, Map<Parametro, Double>> copia = new TreeMap<>();
        porTanque.forEach((k, v) -> copia.put(k, Collections.unmodifiableMap(new EnumMap<>(v))));
        this.porTanque = Collections.unmodifiableMap(copia);
    }

    /** Limites finais de um tanque (padrao de "Todos" + sobrescritas do tanque). */
    public Map<Parametro, Double> limitesDo(int tanque) {
        Map<Parametro, Double> r = new EnumMap<>(Parametro.class);
        r.putAll(todos);
        r.putAll(porTanque.getOrDefault(tanque, Map.of()));
        return r;
    }

    /** Valor final de um parametro de um tanque, se definido. */
    public OptionalDouble valor(int tanque, Parametro p) {
        Double v = limitesDo(tanque).get(p);
        return v == null ? OptionalDouble.empty() : OptionalDouble.of(v);
    }

    /** Valores definidos no bloco "Todos os tanques". */
    public Map<Parametro, Double> padraoTodos() { return todos; }

    /** Numeros dos tanques citados explicitamente no arquivo, em ordem. */
    public Set<Integer> tanquesCitados() { return porTanque.keySet(); }

    /** JSON simples, util para integrar com outros sistemas. */
    public String paraJson() {
        StringBuilder sb = new StringBuilder("{\n  \"todos\": ");
        sb.append(json(todos));
        sb.append(",\n  \"tanques\": {");
        Iterator<Integer> it = porTanque.keySet().iterator();
        while (it.hasNext()) {
            int t = it.next();
            sb.append("\n    \"").append(t).append("\": ").append(json(limitesDo(t)));
            if (it.hasNext()) sb.append(',');
        }
        sb.append(porTanque.isEmpty() ? "}" : "\n  }").append("\n}");
        return sb.toString();
    }

    private static String json(Map<Parametro, Double> m) {
        StringJoiner j = new StringJoiner(", ", "{", "}");
        m.forEach((p, v) -> j.add("\"" + p.nome + "\": " + formatar(v)));
        return j.toString();
    }

    static String formatar(double v) {
        return v == Math.rint(v) ? String.valueOf((long) v) : String.valueOf(v);
    }
}

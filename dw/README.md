# Linguagem .dw: limites de alerta dos tanques

## Para o PO: como editar um arquivo .dw

Abra o arquivo `.dw` em qualquer editor de texto (Bloco de Notas, VS Code...) e escreva assim:

```
Tanque 1
VazaoMin: 200
NivelMax: 90

Tanque 2
VazaoMin: 100
NivelMax: 100
```

Para valer para **todos os tanques** de uma vez:

```
Todos os tanques:
VazaoMin: 200
NivelMax: 90
```

Também dá para misturar. **O que for escrito no tanque vence o "Todos os tanques"**:

```
Todos os tanques:
VazaoMin: 200
NivelMax: 90

Tanque 2          # o Tanque 2 é diferente: só o NivelMax muda
NivelMax: 100
```

Resultado: o Tanque 2 fica com `VazaoMin 200` (veio do "Todos") e `NivelMax 100`.

### Limites disponíveis

| Limite     | O que é                    | Valores aceitos |
|------------|----------------------------|-----------------|
| `VazaoMin` | Vazão mínima               | 0 ou mais       |
| `VazaoMax` | Vazão máxima               | 0 ou mais       |
| `NivelMin` | Nível mínimo (%)           | 0 a 100         |
| `NivelMax` | Nível máximo (%)           | 0 a 100         |

### Regras (são só estas)

- Uma informação por linha.
- `#` serve para anotações: o que vem depois dele é ignorado.
- Linhas em branco podem ficar à vontade.
- Maiúsculas, minúsculas e acentos não importam: `vazão min`, `VAZAOMIN` e `VazaoMin` funcionam igual.
- Os `:` depois de "Tanque 1" são opcionais. Nos limites, pode usar `:` ou `=`.
- Decimais com vírgula ou ponto: `10,5` ou `10.5`. O `%` no final é opcional: `NivelMax: 90%`.

### Conferir se o arquivo está certo

```
java -jar dw.jar tanques.dw
```

Se tiver algo errado, o sistema mostra **todos os problemas de uma vez**, com o número da linha:

```
Encontrei 3 problemas no arquivo:
  - Linha 4: "VazaoMinn" nao e um limite conhecido. Voce quis dizer "VazaoMin"?
  - Linha 5: O valor de "NivelMax" precisa ser um numero (recebi "noventa"). Ex.: NivelMax: 100
  - Linha 8: "NivelMax: 150" esta fora do permitido (de 0 a 100).
```

Ele também avisa se um limite foi escrito duas vezes no mesmo tanque, se um tanque ficou vazio
ou se o mínimo ficou maior que o máximo.

---

## Para os devs

Java 17+ e nenhuma dependência.

### Compilar

```bash
javac -d out src/dw/*.java
printf 'Main-Class: dw.Main\n' > manifest.txt
jar cfm dw.jar manifest.txt -C out .
```

### Linha de comando

```bash
java -jar dw.jar tanques.dw          # valida e mostra o resultado
java -jar dw.jar tanques.dw --json   # resultado em JSON
```

Códigos de saída: `0` = ok, `1` = arquivo com erros, `2` = arquivo não encontrado / uso incorreto.
Dá para usar no CI para barrar um `.dw` inválido antes do deploy.

### Usar no código

```java
Configuracao cfg = LeitorDw.lerArquivo(Path.of("tanques.dw"));   // ou LeitorDw.ler(String)

Map<Parametro, Double> limites = cfg.limitesDo(2);    // já junta "Todos" + "Tanque 2"
OptionalDouble vazaoMin = cfg.valor(2, Parametro.VAZAO_MIN);

cfg.padraoTodos();     // valores do bloco "Todos os tanques"
cfg.tanquesCitados();  // tanques escritos explicitamente no arquivo
cfg.paraJson();
```

`ErroDw` traz a lista estruturada em `problemas()` (linha + mensagem), caso queiram exibir numa tela.

Um tanque que não aparece no arquivo recebe só os valores de "Todos os tanques" em `limitesDo(n)`.

### Adicionar um limite novo

Uma linha em `Parametro.java`:

```java
TEMPERATURA_MAX("TemperaturaMax", -50, 150),
```

Leitura, validação de faixa, sugestão de erro de digitação e JSON passam a funcionar sem mais mudanças.
Se ele tiver um par mínimo/máximo, adicione um `checar(...)` em `LeitorDw.validarMinMenorQueMax`.

### Estrutura

```
src/dw/Parametro.java      limites aceitos e suas faixas
src/dw/LeitorDw.java       parser + validações
src/dw/Configuracao.java   resultado (com a regra "tanque vence Todos")
src/dw/ErroDw.java         erros com número da linha
src/dw/Main.java           linha de comando
exemplos/tanques.dw        exemplo válido
exemplos/com_erros.dw      exemplo com erros, para ver as mensagens
```

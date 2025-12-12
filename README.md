# Gerador de Cards (LLM)

Aplicação desktop (Python + Tkinter) para **gerar cards de tarefa** e **analisar cards/informações** usando um LLM via **OpenRouter**. O app usa templates em `resources/templates.txt` e prompts base em `resources/*.txt`.

## Funcionalidades

- **Análise de Informações**: avalia se as informações fornecidas são suficientes para montar um card no template escolhido.
- **Criação de Card**: gera um card preenchido a partir de um template + descrição em linguagem natural.
- **Análise de Card**: avalia clareza, aderência ao modelo e possíveis ambiguidades de um card já pronto.
- **Informações adicionais**: permite carregar um arquivo (`.txt/.md/.rst`) com contexto do projeto para enriquecer os prompts.

## Requisitos

- **Python 3.10+** (o projeto usa tipagem com `str | None`).

## Instalação

Crie um ambiente virtual (opcional, mas recomendado) e instale as dependências:

```bash
python -m venv .venv
```

Ative o ambiente virtual:

- Windows (PowerShell):

```powershell
.venv\Scripts\Activate.ps1
```

Instale as libs necessárias:

```bash
pip install requests python-dotenv
```

## Configuração (.env)

1. Copie o arquivo `sample.env` para `.env`.
2. Preencha as variáveis:

- **`OPENROUTER_API_KEY`** (ou `API_KEY`): sua chave do OpenRouter
- **Modelos** 
- `MODELO_VALIDACAO_INFO`, `MODELO_CRIACAO`, `MODELO_ANALISE` (como no `sample.env`)

Para escolher modelos válidos, consulte a lista de modelos do OpenRouter em [OpenRouter Models](https://openrouter.ai/models).

## Como executar

Com o `.env` configurado, execute:

```bash
python cards_llm.py
```

O aplicativo abrirá uma janela com 3 abas:

- **Análise de Informações**
- **Criação de Card**
- **Análise de Card**

## Templates de card

Os templates ficam em `resources/templates.txt` e são lidos no formato:

```text
<tipo>
...conteúdo do template...
</tipo>
```

O nome da tag (ex.: `<bug>...</bug>`, `<feature>...</feature>`) vira o **“Tipo de card”** que aparece no dropdown da interface.

## Prompts (resources)

- `resources/creation_prompt.txt`: prompt usado para gerar o card final (retorno esperado entre `<card>...</card>`).
- `resources/info_validation_prompt.txt`: prompt para avaliar suficiência das informações (retorno esperado entre `<info_validacao>...</info_validacao>`).
- `resources/analisys_prompt.txt`: prompt para analisar um card pronto (retorno esperado entre `<analise>...</analise>`).

## Solução de problemas

- **“Chave de API não configurada…”**: crie/ajuste o `.env` com `OPENROUTER_API_KEY` (ou `API_KEY`).
- **“Modelos LLM não configurados…”**: defina os 3 modelos no `.env` (validação/criação/análise).
- **“Arquivo de templates não encontrado…”**: confirme a pasta `resources/` e o arquivo `resources/templates.txt` no mesmo diretório do `cards_llm.py`.

## Estrutura do projeto

```text
.
├─ cards_llm.py
├─ resources/
│  ├─ templates.txt
│  ├─ creation_prompt.txt
│  ├─ info_validation_prompt.txt
│  └─ analisys_prompt.txt
└─ sample.env
```



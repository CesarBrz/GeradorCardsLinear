import os
import re
import threading
import time
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

from dotenv import load_dotenv
import requests


RESOURCES_DIR = "resources"
TEMPLATES_FILE = os.path.join(RESOURCES_DIR, "templates.txt")
CREATION_PROMPT_FILE = os.path.join(RESOURCES_DIR, "creation_prompt.txt")
ANALISYS_PROMPT_FILE = os.path.join(RESOURCES_DIR, "analisys_prompt.txt")
INFO_VALIDATION_PROMPT_FILE = os.path.join(RESOURCES_DIR, "info_validation_prompt.txt")


def load_templates(path: str) -> dict:
    """
    Lê o arquivo de templates e extrai cada card definido entre tags,
    por exemplo: <bug>...</bug>, <chore>...</chore>, etc.
    Retorna um dicionário {nome_tag: conteudo_do_template}.
    """
    try:
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
    except FileNotFoundError:
        raise FileNotFoundError(f"Arquivo de templates não encontrado: {path}")

    # Captura qualquer coisa entre <tag>...</tag> usando o mesmo nome de tag
    pattern = re.compile(r"<(\w+)>(.*?)</\1>", re.DOTALL)
    templates = {}

    for match in pattern.finditer(text):
        tag_name = match.group(1).strip()
        content = match.group(2).strip()
        if tag_name:
            templates[tag_name] = content

    if not templates:
        raise ValueError(
            "Nenhum template encontrado em templates.txt. "
            "Verifique se as tags <tipo>...</tipo> estão corretas."
        )

    return templates


def load_file(path: str) -> str:
    """Carrega um arquivo de texto inteiro."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        raise FileNotFoundError(f"Arquivo não encontrado: {path}")

class CardPromptApp(tk.Tk):
    def __init__(
        self,
        templates: dict,
        validation_model: str,
        creation_model: str,
        analisys_model: str,
    ) -> None:
        super().__init__()
        self.title("Gerador de Cards de Tarefa (LLM)")
        self.geometry("1000x750")

        # Controle de estado de chamadas ao LLM
        self._llm_running = False

        self.templates = templates
        self.additional_info: str = ""
        self.additional_info_filename: str | None = None

        # Modelos LLM
        self.validation_model = validation_model
        self.creation_model = creation_model
        self.analisys_model = analisys_model

        # Carrega os prompts base (templates de prompt)
        self.creation_prompt = load_file(CREATION_PROMPT_FILE)
        self.analisys_prompt = load_file(ANALISYS_PROMPT_FILE)
        self.info_validation_prompt = load_file(INFO_VALIDATION_PROMPT_FILE)

        # Controle de cronômetro
        self._timer_start: float | None = None
        self._timer_job: str | None = None

        self._build_ui()

    # ------------------------------------------------------------------
    # UI principal (Notebook com abas)
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)
        self.rowconfigure(2, weight=0)

        # Barra superior para carregamento de informações adicionais do projeto
        top_frame = ttk.Frame(self)
        top_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 5))
        top_frame.columnconfigure(1, weight=1)

        load_button = ttk.Button(
            top_frame,
            text="Carregar informações de projeto",
            command=self.load_additional_info,
        )
        load_button.grid(row=0, column=0, sticky="w")

        self.additional_info_label_var = tk.StringVar(
            value="Nenhum arquivo de informações de projeto carregado."
        )
        additional_label = ttk.Label(
            top_frame,
            textvariable=self.additional_info_label_var,
            foreground="gray",
        )
        additional_label.grid(row=0, column=1, sticky="w", padx=(10, 0))

        notebook = ttk.Notebook(self)
        notebook.grid(row=1, column=0, sticky="nsew")

        # Abas
        self.tab_info = ttk.Frame(notebook)
        self.tab_create = ttk.Frame(notebook)
        self.tab_analyse = ttk.Frame(notebook)

        notebook.add(self.tab_info, text="Análise de Informações")
        notebook.add(self.tab_create, text="Criação de Card")
        notebook.add(self.tab_analyse, text="Análise de Card")

        self._build_tab_info()
        self._build_tab_create()
        self._build_tab_analyse()

        # Barra de status / progresso (linha inferior)
        status_frame = ttk.Frame(self)
        status_frame.grid(row=2, column=0, sticky="ew", padx=10, pady=(0, 10))
        status_frame.columnconfigure(0, weight=1)
        status_frame.columnconfigure(1, weight=0)
        status_frame.columnconfigure(2, weight=0)

        self.status_var = tk.StringVar(value="Pronto.")
        self.status_label = ttk.Label(status_frame, textvariable=self.status_var)
        self.status_label.grid(row=0, column=0, sticky="w")

        self.timer_var = tk.StringVar(value="Tempo: 00:00")
        self.timer_label = ttk.Label(status_frame, textvariable=self.timer_var)
        self.timer_label.grid(row=0, column=1, sticky="e", padx=(10, 10))

        self.progressbar = ttk.Progressbar(
            status_frame, mode="indeterminate", length=160
        )
        self.progressbar.grid(row=0, column=2, sticky="e")

    # ------------------------------------------------------------------
    # Aba 1: Análise de informações fornecidas (info_validation_prompt)
    # ------------------------------------------------------------------
    def _build_tab_info(self) -> None:
        tab = self.tab_info
        tab.columnconfigure(0, weight=1)
        tab.rowconfigure(3, weight=1)
        tab.rowconfigure(5, weight=1)

        # Linha 0: seleção de tipo de card
        type_frame = ttk.Frame(tab)
        type_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 5))
        type_frame.columnconfigure(1, weight=1)

        ttk.Label(type_frame, text="Tipo de card (template):").grid(
            row=0, column=0, sticky="w", padx=(0, 5)
        )

        self.card_type_info_var = tk.StringVar()
        type_values = sorted(self.templates.keys())
        self.card_type_info_combo = ttk.Combobox(
            type_frame,
            textvariable=self.card_type_info_var,
            values=type_values,
            state="readonly",
        )
        if type_values:
            self.card_type_info_combo.current(0)
        self.card_type_info_combo.grid(row=0, column=1, sticky="ew")

        # Linha 1: instruções
        ttk.Label(
            tab,
            text=(
                "Forneça abaixo, em linguagem natural, as informações sobre a tarefa.\n"
                "A análise gerada pelo LLM avaliará se essas informações são suficientes para montar o card no modelo padrão."
            ),
        ).grid(row=1, column=0, sticky="w", padx=10)

        # Linha 2-3: entrada de informações do usuário
        input_frame = ttk.LabelFrame(tab, text="Informações fornecidas pelo usuário")
        input_frame.grid(row=3, column=0, sticky="nsew", padx=10, pady=(10, 5))
        input_frame.rowconfigure(0, weight=1)
        input_frame.columnconfigure(0, weight=1)

        self.user_info_validation_text = tk.Text(input_frame, wrap="word", height=10)
        self.user_info_validation_text.grid(row=0, column=0, sticky="nsew")

        input_scroll = ttk.Scrollbar(
            input_frame, orient="vertical", command=self.user_info_validation_text.yview
        )
        input_scroll.grid(row=0, column=1, sticky="ns")
        self.user_info_validation_text.configure(yscrollcommand=input_scroll.set)

        # Linha 4: botões
        button_frame = ttk.Frame(tab)
        button_frame.grid(row=4, column=0, sticky="ew", padx=10, pady=5)
        button_frame.columnconfigure(0, weight=1)
        button_frame.columnconfigure(1, weight=0)

        self.generate_info_button = ttk.Button(
            button_frame,
            text="Gerar Análise de Informações",
            command=self.generate_info_validation_prompt,
        )
        self.generate_info_button.grid(row=0, column=0, sticky="w")

        self.copy_button_info = ttk.Button(
            button_frame,
            text="Copiar Análise",
            command=self.copy_prompt_info,
        )
        self.copy_button_info.grid(row=0, column=1, sticky="e", padx=(5, 0))

        # Linha 5: saída (análise do LLM)
        output_frame = ttk.LabelFrame(tab, text="Análise de informações (resposta do LLM)")
        output_frame.grid(row=5, column=0, sticky="nsew", padx=10, pady=(5, 10))
        output_frame.rowconfigure(0, weight=1)
        output_frame.columnconfigure(0, weight=1)

        self.output_text_info = tk.Text(output_frame, wrap="word")
        self.output_text_info.grid(row=0, column=0, sticky="nsew")

        output_scroll = ttk.Scrollbar(
            output_frame, orient="vertical", command=self.output_text_info.yview
        )
        output_scroll.grid(row=0, column=1, sticky="ns")
        self.output_text_info.configure(yscrollcommand=output_scroll.set)

    # ------------------------------------------------------------------
    # Aba 2: Criação de card
    # ------------------------------------------------------------------
    def _build_tab_create(self) -> None:
        tab = self.tab_create
        tab.columnconfigure(0, weight=1)
        tab.rowconfigure(3, weight=1)
        tab.rowconfigure(5, weight=1)

        # Linha 0: seleção de tipo de card
        type_frame = ttk.Frame(tab)
        type_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 5))
        type_frame.columnconfigure(1, weight=1)

        ttk.Label(type_frame, text="Tipo de card (template):").grid(
            row=0, column=0, sticky="w", padx=(0, 5)
        )

        self.card_type_var = tk.StringVar()
        type_values = sorted(self.templates.keys())
        self.card_type_combo = ttk.Combobox(
            type_frame,
            textvariable=self.card_type_var,
            values=type_values,
            state="readonly",
        )
        if type_values:
            self.card_type_combo.current(0)
        self.card_type_combo.grid(row=0, column=1, sticky="ew")

        # Linha 1: instruções
        ttk.Label(
            tab,
            text=(
                "1) Escolha o tipo de card\n"
                "2) Descreva em linguagem natural as informações da tarefa\n"
                "3) Clique em 'Gerar Card' para gerar o card preenchido pelo LLM"
            ),
        ).grid(row=1, column=0, sticky="w", padx=10)

        # Linha 2-3: entrada de informações do usuário
        input_frame = ttk.LabelFrame(tab, text="Informações fornecidas pelo usuário")
        input_frame.grid(row=3, column=0, sticky="nsew", padx=10, pady=(10, 5))
        input_frame.rowconfigure(0, weight=1)
        input_frame.columnconfigure(0, weight=1)

        self.user_input_text = tk.Text(input_frame, wrap="word", height=10)
        self.user_input_text.grid(row=0, column=0, sticky="nsew")

        input_scroll = ttk.Scrollbar(
            input_frame, orient="vertical", command=self.user_input_text.yview
        )
        input_scroll.grid(row=0, column=1, sticky="ns")
        self.user_input_text.configure(yscrollcommand=input_scroll.set)

        # Linha 4: botões
        button_frame = ttk.Frame(tab)
        button_frame.grid(row=4, column=0, sticky="ew", padx=10, pady=5)
        button_frame.columnconfigure(0, weight=1)
        button_frame.columnconfigure(1, weight=0)

        self.generate_button = ttk.Button(
            button_frame, text="Gerar Card", command=self.generate_creation_prompt
        )
        self.generate_button.grid(row=0, column=0, sticky="w")

        self.copy_button_create = ttk.Button(
            button_frame, text="Copiar Card", command=self.copy_prompt_create
        )
        self.copy_button_create.grid(row=0, column=1, sticky="e", padx=(5, 0))

        # Linha 5: saída (card gerado)
        output_frame = ttk.LabelFrame(tab, text="Card gerado pelo LLM")
        output_frame.grid(row=5, column=0, sticky="nsew", padx=10, pady=(5, 10))
        output_frame.rowconfigure(0, weight=1)
        output_frame.columnconfigure(0, weight=1)

        self.output_text_create = tk.Text(output_frame, wrap="word")
        self.output_text_create.grid(row=0, column=0, sticky="nsew")

        output_scroll = ttk.Scrollbar(
            output_frame, orient="vertical", command=self.output_text_create.yview
        )
        output_scroll.grid(row=0, column=1, sticky="ns")
        self.output_text_create.configure(yscrollcommand=output_scroll.set)

    # ------------------------------------------------------------------
    # Aba 2: Análise de card pronto (Card_para_analise)
    # ------------------------------------------------------------------
    def _build_tab_analyse(self) -> None:
        tab = self.tab_analyse
        tab.columnconfigure(0, weight=1)
        tab.rowconfigure(3, weight=1)
        tab.rowconfigure(5, weight=1)

        # Linha 0: seleção de tipo de card
        type_frame = ttk.Frame(tab)
        type_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 5))
        type_frame.columnconfigure(1, weight=1)

        ttk.Label(type_frame, text="Tipo de card (template de referência):").grid(
            row=0, column=0, sticky="w", padx=(0, 5)
        )

        self.card_type_analyse_var = tk.StringVar()
        type_values = sorted(self.templates.keys())
        self.card_type_analyse_combo = ttk.Combobox(
            type_frame,
            textvariable=self.card_type_analyse_var,
            values=type_values,
            state="readonly",
        )
        if type_values:
            self.card_type_analyse_combo.current(0)
        self.card_type_analyse_combo.grid(row=0, column=1, sticky="ew")

        # Linha 1: instruções
        ttk.Label(
            tab,
            text=(
                "Cole abaixo o card já preenchido que deseja analisar.\n"
                "A análise gerada pelo LLM avaliará clareza, aderência ao modelo "
                "e possíveis ambiguidades."
            ),
        ).grid(row=1, column=0, sticky="w", padx=10)

        # Linha 2-3: entrada de card para análise
        input_frame = ttk.LabelFrame(tab, text="Card para análise")
        input_frame.grid(row=3, column=0, sticky="nsew", padx=10, pady=(10, 5))
        input_frame.rowconfigure(0, weight=1)
        input_frame.columnconfigure(0, weight=1)

        self.card_to_analyse_text = tk.Text(input_frame, wrap="word", height=10)
        self.card_to_analyse_text.grid(row=0, column=0, sticky="nsew")

        input_scroll = ttk.Scrollbar(
            input_frame, orient="vertical", command=self.card_to_analyse_text.yview
        )
        input_scroll.grid(row=0, column=1, sticky="ns")
        self.card_to_analyse_text.configure(yscrollcommand=input_scroll.set)

        # Linha 4: botões
        button_frame = ttk.Frame(tab)
        button_frame.grid(row=4, column=0, sticky="ew", padx=10, pady=5)
        button_frame.columnconfigure(0, weight=1)
        button_frame.columnconfigure(1, weight=0)

        self.generate_analisys_button = ttk.Button(
            button_frame, text="Gerar Análise do Card", command=self.generate_analisys_prompt
        )
        self.generate_analisys_button.grid(row=0, column=0, sticky="w")

        self.copy_button_analyse = ttk.Button(
            button_frame, text="Copiar Análise", command=self.copy_prompt_analyse
        )
        self.copy_button_analyse.grid(row=0, column=1, sticky="e", padx=(5, 0))

        # Linha 5: saída (análise do card)
        output_frame = ttk.LabelFrame(tab, text="Análise do card (resposta do LLM)")
        output_frame.grid(row=5, column=0, sticky="nsew", padx=10, pady=(5, 10))
        output_frame.rowconfigure(0, weight=1)
        output_frame.columnconfigure(0, weight=1)

        self.output_text_analyse = tk.Text(output_frame, wrap="word")
        self.output_text_analyse.grid(row=0, column=0, sticky="nsew")

        output_scroll = ttk.Scrollbar(
            output_frame, orient="vertical", command=self.output_text_analyse.yview
        )
        output_scroll.grid(row=0, column=1, sticky="ns")
        self.output_text_analyse.configure(yscrollcommand=output_scroll.set)

    # ------------------------------------------------------------------
    # Lógica de geração de prompts + chamada ao LLM
    # ------------------------------------------------------------------
    def _apply_common_replacements(self, prompt: str) -> str:
        """Aplica substituições comuns a todos os prompts."""
        return prompt.replace("{informacoes_adicionais}", self.additional_info or "")

    def _get_template_for_type(self, card_type: str) -> str | None:
        card_type = card_type.strip()
        if not card_type:
            return None
        return self.templates.get(card_type)

    def _call_llm(self, prompt: str, model_name: str) -> str:
        """
        Envia o prompt ao LLM via OpenRouter e retorna o texto de resposta.
        Dispara exceção em caso de erro (tratada pela thread chamadora).
        """
        api_key = os.getenv("OPENROUTER_API_KEY") or os.getenv("API_KEY")
        if not api_key:
            raise RuntimeError(
                "Chave de API do OpenRouter não configurada. "
                "Defina OPENROUTER_API_KEY ou API_KEY no arquivo .env."
            )

        url = "https://openrouter.ai/api/v1/chat/completions"
        payload = {
            "model": model_name,
            "messages": [
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
        }

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        response = requests.post(url, json=payload, headers=headers, timeout=60)
        response.raise_for_status()
        data = response.json()

        try:
            text = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as exc:
            raise RuntimeError("Resposta inválida do modelo OpenRouter.") from exc

        return text.strip()

    def _start_timer(self) -> None:
        """Inicia o cronômetro em tempo real."""
        self._timer_start = time.time()
        self._update_timer()

    def _update_timer(self) -> None:
        """Atualiza o texto do cronômetro enquanto estiver rodando."""
        if self._timer_start is None:
            return
        elapsed = int(time.time() - self._timer_start)
        minutes, seconds = divmod(elapsed, 60)
        self.timer_var.set(f"Tempo: {minutes:02d}:{seconds:02d}")
        # Agenda próxima atualização
        self._timer_job = self.after(500, self._update_timer)

    def _stop_timer(self) -> None:
        """Para o cronômetro e mantém o último valor até a próxima execução."""
        if self._timer_job is not None:
            try:
                self.after_cancel(self._timer_job)
            except Exception:
                pass
        self._timer_job = None
        self._timer_start = None

    def _set_busy(self, busy: bool, message: str | None = None) -> None:
        """Atualiza barra de status, progress bar e botões."""
        if message is not None:
            self.status_var.set(message)

        widgets_to_toggle = [
            getattr(self, "generate_button", None),
            getattr(self, "generate_info_button", None),
            getattr(self, "generate_analisys_button", None),
        ]

        state = "disabled" if busy else "normal"
        for w in widgets_to_toggle:
            if w is not None:
                w.configure(state=state)

        if busy:
            # Inicia cronômetro e progress bar
            self._start_timer()
            self.progressbar.start(80)
        else:
            # Para cronômetro e progress bar
            self._stop_timer()
            self.progressbar.stop()

    def _run_llm_async(
        self,
        prompt: str,
        model_name: str,
        tag_name: str,
        output_widget: tk.Text,
        busy_message: str,
    ) -> None:
        """
        Executa a chamada ao LLM em uma thread separada e atualiza a GUI ao final.
        """
        if self._llm_running:
            messagebox.showinfo(
                "Aguarde",
                "Já existe uma chamada ao LLM em andamento. Aguarde a finalização.",
            )
            return

        # Limpa imediatamente a saída para evitar confusão com resultados anteriores
        output_widget.delete("1.0", tk.END)

        self._llm_running = True
        self._set_busy(True, busy_message)

        def worker() -> None:
            error: str | None = None
            llm_clean: str = ""
            try:
                llm_raw = self._call_llm(prompt, model_name)
                llm_clean_local = self._extract_tag_content(llm_raw, tag_name)
                llm_clean = llm_clean_local
            except Exception as exc:  # noqa: BLE001 - tratamos no thread principal
                error = str(exc)

            def on_done() -> None:
                if error:
                    messagebox.showerror("Erro ao chamar LLM", error)
                else:
                    output_widget.delete("1.0", tk.END)
                    output_widget.insert("1.0", llm_clean)

                self._set_busy(False, "Pronto.")
                self._llm_running = False

            self.after(0, on_done)

        threading.Thread(target=worker, daemon=True).start()

    @staticmethod
    def _extract_tag_content(text: str, tag_name: str) -> str:
        """
        Extrai o conteúdo entre <tag_name>...</tag_name>.
        Se a tag não for encontrada, retorna o texto original.
        """
        pattern = rf"<\s*{tag_name}\s*>(.*?)</\s*{tag_name}\s*>"
        match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
        if match:
            return match.group(1).strip()
        return text.strip()

    def generate_creation_prompt(self) -> None:
        card_type = self.card_type_var.get().strip()
        if not card_type:
            messagebox.showwarning(
                "Tipo não selecionado", "Selecione um tipo de card na lista."
            )
            return

        template = self._get_template_for_type(card_type)
        if not template:
            messagebox.showerror(
                "Template não encontrado",
                f"Não foi possível encontrar o template para o tipo: {card_type}",
            )
            return

        user_info = self.user_input_text.get("1.0", tk.END).strip()

        prompt = self.creation_prompt.replace("{Card_modelo}", template)
        prompt = prompt.replace("{informacoes_fornecidas_pelo_usuario}", user_info)
        prompt = self._apply_common_replacements(prompt)

        self._run_llm_async(
            prompt=prompt,
            model_name=self.creation_model,
            tag_name="card",
            output_widget=self.output_text_create,
            busy_message="Gerando card com o LLM...",
        )

    def generate_info_validation_prompt(self) -> None:
        card_type = self.card_type_info_var.get().strip()
        if not card_type:
            messagebox.showwarning(
                "Tipo não selecionado", "Selecione um tipo de card na lista."
            )
            return

        template = self._get_template_for_type(card_type)
        if not template:
            messagebox.showerror(
                "Template não encontrado",
                f"Não foi possível encontrar o template para o tipo: {card_type}",
            )
            return

        user_info = self.user_info_validation_text.get("1.0", tk.END).strip()

        prompt = self.info_validation_prompt.replace("{Card_modelo}", template)
        prompt = prompt.replace("{informacoes_fornecidas_pelo_usuario}", user_info)
        prompt = self._apply_common_replacements(prompt)

        self._run_llm_async(
            prompt=prompt,
            model_name=self.validation_model,
            tag_name="info_validacao",
            output_widget=self.output_text_info,
            busy_message="Analisando informações com o LLM...",
        )

    def generate_analisys_prompt(self) -> None:
        card_type = self.card_type_analyse_var.get().strip()
        if not card_type:
            messagebox.showwarning(
                "Tipo não selecionado", "Selecione um tipo de card na lista."
            )
            return

        template = self._get_template_for_type(card_type)
        if not template:
            messagebox.showerror(
                "Template não encontrado",
                f"Não foi possível encontrar o template para o tipo: {card_type}",
            )
            return

        card_to_analyse = self.card_to_analyse_text.get("1.0", tk.END).strip()

        prompt = self.analisys_prompt.replace("{Card_modelo}", template)
        prompt = prompt.replace("{Card_para_analise}", card_to_analyse)
        prompt = self._apply_common_replacements(prompt)

        self._run_llm_async(
            prompt=prompt,
            model_name=self.analisys_model,
            tag_name="analise",
            output_widget=self.output_text_analyse,
            busy_message="Analisando card com o LLM...",
        )

    # ------------------------------------------------------------------
    # Copiar resultados (cards/análises) para clipboard
    # ------------------------------------------------------------------
    def _copy_to_clipboard(self, text_widget: tk.Text, titulo: str) -> None:
        prompt = text_widget.get("1.0", tk.END).strip()
        if not prompt:
            messagebox.showinfo(
                "Nada para copiar",
                "Gere um resultado com o LLM antes de copiar para a área de transferência.",
            )
            return
        self.clipboard_clear()
        self.clipboard_append(prompt)
        self.update()
        messagebox.showinfo("Copiado", f"{titulo} copiado para a área de transferência.")

    def copy_prompt_create(self) -> None:
        self._copy_to_clipboard(self.output_text_create, "Card")

    def copy_prompt_analyse(self) -> None:
        self._copy_to_clipboard(self.output_text_analyse, "Análise do card")

    def copy_prompt_info(self) -> None:
        self._copy_to_clipboard(self.output_text_info, "Análise de informações")

    # ------------------------------------------------------------------
    # Carregar informações adicionais de projeto
    # ------------------------------------------------------------------
    def load_additional_info(self) -> None:
        file_path = filedialog.askopenfilename(
            title="Selecionar arquivo de informações de projeto",
            filetypes=(
                ("Arquivos de texto", "*.txt;*.md;*.rst"),
                ("Todos os arquivos", "*.*"),
            ),
        )
        if not file_path:
            return

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                self.additional_info = f.read().strip()
            self.additional_info_filename = file_path
            # Mostra apenas o nome do arquivo na barra
            display_name = file_path.split("/")[-1].split("\\")[-1]
            self.additional_info_label_var.set(
                f"Informações de projeto carregadas de: {display_name}"
            )
        except Exception as exc:  # noqa: BLE001 - simples para GUI
            messagebox.showerror(
                "Erro ao carregar arquivo de informações de projeto", str(exc)
            )


def main() -> None:
    try:
        # Carrega variáveis de ambiente (.env)
        load_dotenv()
        # Suporta tanto OPENROUTER_API_KEY quanto um possível alias API_KEY
        api_key = os.getenv("OPENROUTER_API_KEY") or os.getenv("API_KEY")
        if not api_key:
            raise RuntimeError(
                "Chave de API não configurada. "
                "Defina OPENROUTER_API_KEY ou API_KEY no arquivo .env com a chave de API do OpenRouter."
            )

        # Modelos podem ser configurados com dois conjuntos de nomes:
        # - LLM_MODEL_VALIDATION / LLM_MODEL_CREATION / LLM_MODEL_ANALYSIS
        # - MODELO_VALIDACAO_INFO / MODELO_CRIACAO / MODELO_ANALISE (como no sample.env)
        validation_model = os.getenv("LLM_MODEL_VALIDATION") or os.getenv(
            "MODELO_VALIDACAO_INFO"
        )
        creation_model = os.getenv("LLM_MODEL_CREATION") or os.getenv("MODELO_CRIACAO")
        analisys_model = os.getenv("LLM_MODEL_ANALYSIS") or os.getenv("MODELO_ANALISE")

        if not (validation_model and creation_model and analisys_model):
            raise RuntimeError(
                "Modelos LLM não configurados. "
                "Defina LLM_MODEL_VALIDATION / LLM_MODEL_CREATION / LLM_MODEL_ANALYSIS "
                "ou MODELO_VALIDACAO_INFO / MODELO_CRIACAO / MODELO_ANALISE no .env."
            )

        templates = load_templates(TEMPLATES_FILE)
    except Exception as exc:  # noqa: BLE001 - simples para GUI
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror("Erro ao carregar arquivos", str(exc))
        root.destroy()
        return

    app = CardPromptApp(
        templates,
        validation_model=validation_model,
        creation_model=creation_model,
        analisys_model=analisys_model,
    )
    app.mainloop()


if __name__ == "__main__":
    main()



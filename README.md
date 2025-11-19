# Projeto-Integrado-ferramenta-escolar-

README – Plataforma de Estudos 8BIT-Devs (Python + Tkinter)

Descrição do Projeto

Este projeto é uma plataforma acadêmica desenvolvida em Python, utilizando Tkinter para interface gráfica.
O sistema simula um ambiente educacional completo, permitindo que alunos, professores e administradores realizem diferentes operações, como login, visualização de atividades, envio de trabalhos, atribuição de notas, cálculo de médias e gerenciamento de dados.

O projeto também utiliza:

DLL externa (notas.dll) para cálculo de médias em C.

Banco de dados em arquivos JSON para armazenamento local.

Recursos de acessibilidade, como narração (TTS), alto contraste e texto ampliado.

Sistema de encriptação simples para proteger informações sensíveis.

Funcionalidades Principais
Aluno

Visualizar atividades pendentes

Enviar respostas para tarefas

Consultar notas por semestre

Acessar calendário de atividades

Professor

Criar novas atividades com anexos

Atribuir notas aos alunos

Marcar faltas

Analisar desempenho da turma com gráficos

Ver submissões e corrigir trabalhos

Administrativo

Criar usuários (alunos e professores)

Gerenciar dados cadastrados

Acessar todas as funções de professor

Acessibilidade

Narração por voz (TTS)

Modo alto contraste

Texto grande

Orientações guiadas por voz

Segurança e Armazenamento

Criptografia simples em dados sensíveis (nome, senha, CPF, e-mail etc.)

Banco de dados local baseado em JSON

Pasta dedicada a anexos de atividades

Tecnologias Utilizadas

Python 3.x

Tkinter (Interface gráfica)

JSON (Banco de dados local)

ctypes + DLL em C para cálculo de médias

pyttsx3 (TTS – opcional)

matplotlib (Gráficos — opcional)

Pathlib / OS / Shutil (Sistema de arquivos)

Estrutura do Projeto
/Projeto
│-- main.py
│-- notas.dll
│-- /BD
│     ├── BD_A.json        (Alunos)
│     ├── BD_P.json        (Professores)
│     ├── BD_AD.json       (Administrativo)
│     ├── BD_ACT.json      (Atividades)
│     └── attachments/     (Anexos enviados)

Como Executar

Certifique-se de que o Python 3 está instalado.

Coloque o arquivo notas.dll na mesma pasta do main.py.

Execute:

python main.py


Se desejar usar TTS:

pip install pyttsx3


Para gráficos:

pip install matplotlib

Destaques do Código

Modularização com funções internas organizadas por fluxo (dashboard, login, atividades etc.)

Uso de classes C via DLL para cálculos de desempenho

Funções de utilidade para encriptar/decriptar campos

Painéis dinâmicos para aluno, professor e admin

Sistema de anexos registrado no próprio diretório do projeto

Possíveis Melhorias Futuras

Migrar para um banco SQL (SQLite ou PostgreSQL)

Criar API REST para separar backend e frontend

Adicionar design responsivo usando frameworks como Flask + HTML/CSS

Criar testes automatizados (pytest)

Autor

João Pedro Silva
Estudante de Análise e Desenvolvimento de Sistemas

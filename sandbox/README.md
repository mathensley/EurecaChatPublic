# Sandbox de execução

O backend usa `microsandbox==0.7.2` para criar uma microVM por chamada de `execute_bash`. Ela recebe apenas o `sandbox/` da conversa em `/workspace` (leitura e escrita) e o `exports/` da conversa em `/exports` (somente leitura). Os arquivos `/skills` e as bibliotecas Python já estão na imagem `eureca-sandbox:0.1.0`. A rede da microVM é desativada. Ao terminar o comando, a microVM é removida; os arquivos da conversa continuam no volume `eureca_workdirs` até a exclusão do chat ou a desconexão anônima.

O backend precisa de `/dev/kvm` funcional no host e no container.

## Deploy automático

O mesmo comando de deploy do sistema prepara o sandbox:

```bash
docker compose --profile observability up -d --build
```

Durante o build, o Dockerfile principal instala as bibliotecas em um estágio isolado e empacota esse filesystem como uma imagem OCI dentro da imagem do backend. Antes de iniciar o servidor, `entrypoint.sh` executa `sandbox.ensure_image`: ele carrega essa imagem no cache do microsandbox se ela ainda não estiver lá ou se o conteúdo tiver mudado. Não é necessário rodar `sandbox/prepare.sh`, montar o socket do Docker ou instalar pacotes quando cada microVM inicia. O `sandbox/Dockerfile` separado permanece apenas para testes manuais da imagem.

A tool usa `PullPolicy.NEVER`: se a preparação automática falhar, o backend não inicia e não tenta buscar uma imagem não controlada ao atender um usuário.
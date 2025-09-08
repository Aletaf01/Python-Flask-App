# Python Flask web app con Docker, Apparmor e Seccomp 
La nostra applicazione python si trova in [app.py](./app.py), che poi lanciamo dentro un container Docker grazie al nostro [Dockerfile](./Dockerfile)

## Passaggi 

### 1. Istalla
Docker 
- https://wiki.nixos.org/wiki/Docker

Apparmor
- https://search.nixos.org/options?channel=unstable&size=50&sort=relevance&type=packages&query=apparmor
- metti `apparmor-flask` in `/etc/apparmor.d/`

### 2. Nix shell con packages necessary
`, poetry python313Packages.flask apparmor-parser strace websocat python313Packages.requests`

### 3. Build del container docker
`docker build . -t flask:0.0.3`

### 4. Avvia il container docker
```
docker run -it --rm \
        --security-opt seccomp=./seccomp.json \
        --security-opt apparmor=apparmor-flask \
        -p 5000:5000 flask:0.0.3
```

### 5. Genera un file seccomp che abbia solo le systemcall utilizzate dalla nostra applicazione

## Informazioni utili
- Il file apparmor viene specificato nel comando `docker run` con `--security-opt apparmor=apparmor-flask` e si trova in `/etc/apparmor.d/apparmor-flask`
- Nel file apparmor abbiamo `/app/data.txt rw` perche' `app.py` deve poter scrivere in `data.txt`

- Su Azure, il container registry e' un a sorta di cloud per immagini docker
# git Zones Repository SSH Server

Provides *read only* git access to the zones git repository which is stored in volume `zones`.


## Server Authentication

The server identity is based on an ED25519 key pair generated on first startup and stored in the `gitzones_keys` volume.
To make sure clients are connecting to the correct zone server, use the `auth` command of the gitzones container:

    $ docker-compose exec gitzones auth id
    desec.example.dedyn.io ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIKxVBPSvHDFGzorms9x76+nAo7Zs+0PhaKnMblcdVPos root@c269a29f451d

The output can be appended to any client's `~/.ssh/known_hosts` file.


## Client Authentication

To allow clients to read from the zones repository, add their keys to the `gitzones_authorized_keys` file.
This container ships a tool for key management.

To add a key, use

    docker-compose exec gitzones auth add ssh-rsa AAAAB<omitted>= ns23.desec.io

The command line arguments after `auth add` can usually be copied from the client's SSH public key file.
The last argument is the label under which the key is stored.
Unlike SSH, we insist on unique labels for each key.

To remove a key, use

    docker-compose exec gitzones auth rm ns23.desec.io

To list all labels of currently authorized keys,

    docker-compose exec gitzones auth ls

A `-v` flag can be added to also display the keys.
To see the bare contents of the authorized_keys file,

    docker-compose exec gitzones auth cat


## Security Considerations

Read-only access to the repository is enforced by docker volume options.
SSH configuration is pretty restrictive, extra features like X11 forwarding are disabled.
SSH access is only granted via a non-interactive git shell, but all clients share the same UNIX user (`git`).
For mutual authentication, see above.

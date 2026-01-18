# Gamificirana višeagentna simulacija Axelrodovog turnira

Ovaj projekt implementira Axelrodov turnir iterirane dileme zatvorenika kao višeagentni sustav, uz gamifikaciju u tematskom okruženju Game of Thrones. Svaka kuća predstavlja autonomnog agenta s određenom strategijom ponašanja.

Projekt je izrađen u sklopu kolegija Višeagentni sustavi.

## Cilj projekta

formalno modelirati Axelrodov turnir kao MAS

implementirati reaktivne i adaptivne agente

analizirati dugoročno ponašanje strategija

vizualno prikazati odnose suradnje i izdaje

## Načini rada

Simulacijski mod – svi agenti sudjeluju bez eliminacije

Game of Thrones mod – eliminacijski turnir s postupnim izbacivanjem kuća i noise mehanizmom

## Arhitektura

SPADE agenti – kuće

Orchestrator – upravljanje rundama i sinkronizacija

Engine – pravila i bodovanje

Pygame UI – vizualizacija mreže odnosa i statistike

Komunikacija se odvija porukama (XMPP).

## Tehnologije

Python

SPADE 4.1.2

Pygame

ejabberd (XMPP)

WSL

## Pokretanje
`python ui_pygame.py`

.PHONY: review-round

# One AI review round: ROUND=n, or CHECK=1 to check every round's responses; optional ROUNDS (default 2, max 5), MODE=adhoc, CHANGE, MILESTONE, BASE, MODEL.
review-round:
	@test -n "$(ROUND)$(CHECK)" || (echo "usage: make review-round ROUND=n|CHECK=1 [ROUNDS=n] [MODE=adhoc] [CHANGE=..] [MILESTONE=..] [BASE=..] [MODEL=..]" && exit 2)
	@uv run --frozen --project backend python backend/scripts/review_round.py $(if $(CHECK),--check,--round $(ROUND)) $(if $(ROUNDS),--rounds $(ROUNDS)) $(if $(MODE),--mode $(MODE)) \
		$(if $(CHANGE),--change $(CHANGE)) $(if $(MILESTONE),--milestone $(MILESTONE)) \
		$(if $(BASE),--base $(BASE)) $(if $(MODEL),--model $(MODEL))


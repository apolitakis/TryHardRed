@ TryHardRed: the gimmick key items and the Gen 9 Exp. Share.
@ Oak hands them over with the Pokédex. A save that is already past that scene gets them from the next
@ Pokémon Center nurse instead, so old playtest saves catch up.

TryHardRed_EventScript_GiveGimmickKit::
	goto_if_set FLAG_TRH_RECEIVED_GIMMICK_KIT, TryHardRed_EventScript_GiveGimmickKitEnd
	msgbox TryHardRed_Text_TakeTheseTools
	giveitem ITEM_EXP_SHARE
	giveitem ITEM_MEGA_RING
	giveitem ITEM_Z_POWER_RING
	giveitem ITEM_TERA_ORB
	giveitem ITEM_DYNAMAX_BAND
	setflag FLAG_TRH_EXP_SHARE_ON
	setflag FLAG_TRH_TERA_ORB_CHARGED
	setflag FLAG_TRH_RECEIVED_GIMMICK_KIT
	msgbox TryHardRed_Text_ExplainTools
TryHardRed_EventScript_GiveGimmickKitEnd::
	return

TryHardRed_EventScript_NurseGivesGimmickKit::
	goto_if_set FLAG_TRH_RECEIVED_GIMMICK_KIT, TryHardRed_EventScript_GiveGimmickKitEnd
	goto_if_unset FLAG_SYS_POKEDEX_GET, TryHardRed_EventScript_GiveGimmickKitEnd
	msgbox TryHardRed_Text_NurseOakLeftThese
	call TryHardRed_EventScript_GiveGimmickKit
	return

TryHardRed_Text_TakeTheseTools:
	.string "OAK: Oh, and these, too.\p"
	.string "Trainers these days battle with\n"
	.string "all sorts of new tricks.\p"
	.string "You'll want to keep up!$"

TryHardRed_Text_ExplainTools:
	.string "The EXP. SHARE lets your whole team\n"
	.string "learn from every battle.\l"
	.string "Switch it off in your BAG if you like.\p"
	.string "With the rings, the ORB and the BAND,\n"
	.string "your POKéMON can Mega Evolve, use\l"
	.string "Z-Moves, Terastallize or Dynamax.\p"
	.string "Each battle allows only some of them,\n"
	.string "and the rule holds for both sides.\p"
	.string "The TERA ORB recharges whenever\n"
	.string "your POKéMON are healed.$"

TryHardRed_Text_NurseOakLeftThese:
	.string "Oh, {PLAYER}!\n"
	.string "PROF. OAK left these for you.$"

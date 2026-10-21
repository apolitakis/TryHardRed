#include "global.h"
#include "battle.h"
#include "battle_setup.h"
#include "tryhardred_gimmicks.h"
#include "constants/battle.h"
#include "constants/trainers.h"
#include "constants/opponents.h"

#include "data/tryhardred/gimmick_rules.h"

static const u8 sGimmickRuleBits[GIMMICKS_COUNT] =
{
    [GIMMICK_MEGA]        = GIMMICK_RULE_MEGA,
    [GIMMICK_ULTRA_BURST] = GIMMICK_RULE_Z_MOVE,
    [GIMMICK_Z_MOVE]      = GIMMICK_RULE_Z_MOVE,
    [GIMMICK_DYNAMAX]     = GIMMICK_RULE_DYNAMAX,
    [GIMMICK_TERA]        = GIMMICK_RULE_TERA,
};

u32 GetGimmickRuleForTrainer(u32 trainerId)
{
    for (u32 i = 0; i < ARRAY_COUNT(sGimmickRules); i++)
    {
        if (sGimmickRules[i].trainerId == trainerId)
            return sGimmickRules[i].allowed;
    }
    return GIMMICK_RULE_ALL;
}

// In a fight against two trainers, only what both allow.
u32 GetGimmickRuleForBattle(void)
{
    u32 allowed = GIMMICK_RULE_ALL;

    if (!(gBattleTypeFlags & BATTLE_TYPE_TRAINER))
        return allowed;
    if (TRAINER_BATTLE_PARAM.opponentA != TRAINER_NONE)
        allowed &= GetGimmickRuleForTrainer(TRAINER_BATTLE_PARAM.opponentA);
    if ((gBattleTypeFlags & BATTLE_TYPE_TWO_OPPONENTS) && TRAINER_BATTLE_PARAM.opponentB != TRAINER_NONE)
        allowed &= GetGimmickRuleForTrainer(TRAINER_BATTLE_PARAM.opponentB);
    return allowed;
}

bool32 IsGimmickAllowedInBattle(enum Gimmick gimmick)
{
    return (GetGimmickRuleForBattle() & sGimmickRuleBits[gimmick]) != 0;
}

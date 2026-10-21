#ifndef GUARD_TRYHARDRED_GIMMICKS_H
#define GUARD_TRYHARDRED_GIMMICKS_H

#include "battle_gimmick.h"

// TryHardRed: each fight allows a set of battle gimmicks, and the rule binds both sides.
// Ultra Burst rides on the Z-Move bit, since both need the Z-Power Ring.
#define GIMMICK_RULE_MEGA     (1 << 0)
#define GIMMICK_RULE_Z_MOVE   (1 << 1)
#define GIMMICK_RULE_DYNAMAX  (1 << 2)
#define GIMMICK_RULE_TERA     (1 << 3)
#define GIMMICK_RULE_ALL      (GIMMICK_RULE_MEGA | GIMMICK_RULE_Z_MOVE | GIMMICK_RULE_DYNAMAX | GIMMICK_RULE_TERA)

struct GimmickRule
{
    u16 trainerId;
    u8 allowed;
};

u32 GetGimmickRuleForTrainer(u32 trainerId);
u32 GetGimmickRuleForBattle(void);
bool32 IsGimmickAllowedInBattle(enum Gimmick gimmick);

#endif // GUARD_TRYHARDRED_GIMMICKS_H

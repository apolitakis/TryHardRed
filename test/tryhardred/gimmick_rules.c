#include "global.h"
#include "battle.h"
#include "battle_setup.h"
#include "tryhardred_gimmicks.h"
#include "test/test.h"
#include "constants/opponents.h"

TEST("(TryHardRed) Brock's fight allows only Terastal")
{
    EXPECT_EQ(GetGimmickRuleForTrainer(TRAINER_LEADER_BROCK), GIMMICK_RULE_TERA);
}

TEST("(TryHardRed) Trainers without a rule allow all four gimmicks")
{
    EXPECT_EQ(GetGimmickRuleForTrainer(TRAINER_NONE), GIMMICK_RULE_ALL);
}

TEST("(TryHardRed) A fight's gimmick rule binds the battle, wild battles allow all")
{
    u32 savedFlags = gBattleTypeFlags;
    u16 savedOpponent = TRAINER_BATTLE_PARAM.opponentA;

    gBattleTypeFlags = BATTLE_TYPE_TRAINER;
    TRAINER_BATTLE_PARAM.opponentA = TRAINER_LEADER_SABRINA;
    EXPECT(IsGimmickAllowedInBattle(GIMMICK_MEGA));
    EXPECT(!IsGimmickAllowedInBattle(GIMMICK_TERA));
    EXPECT(!IsGimmickAllowedInBattle(GIMMICK_DYNAMAX));
    EXPECT(!IsGimmickAllowedInBattle(GIMMICK_Z_MOVE));
    EXPECT(!IsGimmickAllowedInBattle(GIMMICK_ULTRA_BURST));

    gBattleTypeFlags = 0;
    EXPECT(IsGimmickAllowedInBattle(GIMMICK_TERA));
    EXPECT(IsGimmickAllowedInBattle(GIMMICK_DYNAMAX));

    gBattleTypeFlags = savedFlags;
    TRAINER_BATTLE_PARAM.opponentA = savedOpponent;
}

TEST("(TryHardRed) Gen 9 Exp. Share and Tera Orb use their own saved flags")
{
    EXPECT_EQ(I_EXP_SHARE_FLAG, FLAG_TRH_EXP_SHARE_ON);
    EXPECT_EQ(B_FLAG_TERA_ORB_CHARGED, FLAG_TRH_TERA_ORB_CHARGED);
    EXPECT(I_EXP_SHARE_FLAG > TEMP_FLAGS_END);
}

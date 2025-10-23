-- SQL function to safely increment agent balances
-- This should be run in your Supabase SQL editor

CREATE OR REPLACE FUNCTION increment_agent_balance(
    p_agent_id UUID,
    p_amount DECIMAL(10, 2)
)
RETURNS JSON
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    v_result JSON;
BEGIN
    -- Update the agent balances
    UPDATE "Agent"
    SET
        total_earnings = COALESCE(total_earnings, 0) + p_amount,
        available_balance = COALESCE(available_balance, 0) + p_amount,
        updated_at = NOW()
    WHERE id = p_agent_id
    RETURNING json_build_object(
        'id', id,
        'user_id', user_id,
        'total_earnings', total_earnings,
        'available_balance', available_balance
    ) INTO v_result;

    -- Check if update was successful
    IF v_result IS NULL THEN
        RAISE EXCEPTION 'Agent not found for agent_id: %', p_agent_id;
    END IF;

    RETURN v_result;
END;
$$;

-- Grant execute permission to authenticated users
GRANT EXECUTE ON FUNCTION increment_agent_balance(UUID, DECIMAL) TO authenticated;
GRANT EXECUTE ON FUNCTION increment_agent_balance(UUID, DECIMAL) TO service_role;

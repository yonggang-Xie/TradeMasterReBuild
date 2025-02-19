trainer = dict(
    type = "AlgorithmicTradingTrainer",
    epochs = 20,
    work_dir = "work_dir",
    seeds_list = [12345],
    batch_size = 64,
    horizon_len = 512,
    buffer_size = 1e6,
    num_threads = 8,
    if_remove=False,
    if_discrete = True,
    if_off_policy = True,
    if_keep_save = True,
    if_over_write = False,
    if_save_buffer = False,
    eval_times = 3
)
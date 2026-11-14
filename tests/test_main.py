from gaming_analytics_data_lake import main


def test_main_prints_greeting(capsys):
    main()

    assert capsys.readouterr().out == "Hello from gaming-analytics-data-lake!\n"

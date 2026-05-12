add_executable(design_patterns
        adapter.h
        antipatterns.h
        command.h
        composite.h
        compound.h
        decorator.h
        facade.h
        factory.h
        iterator.h
        observer.h
        proxy.h
        real_world_examples.h
        singleton.h
        state.h
        strategy.h
        template_method.h
        test_design_patterns.cpp
)


target_include_directories(design_patterns PUBLIC .)

target_link_libraries(design_patterns PRIVATE GTest::gtest GTest::gtest_main)

package com.medicalai;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.scheduling.annotation.EnableAsync;

@SpringBootApplication
@EnableAsync
public class MedicalAiApplication {

    public static void main(String[] args) {
        SpringApplication.run(MedicalAiApplication.class, args);
    }
}

package com.medicalai.common.dto;

import jakarta.validation.ConstraintViolation;
import jakarta.validation.Validation;
import jakarta.validation.Validator;
import jakarta.validation.ValidatorFactory;
import org.junit.jupiter.api.AfterAll;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;

import java.util.Set;
import java.util.stream.Collectors;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * 注册请求参数校验单元测试
 * 说明：密码复杂度（长度 / 字符类别）由 PasswordPolicy 在服务层统一校验
 */
class RegisterRequestValidationTest {

    private static ValidatorFactory validatorFactory;
    private static Validator validator;

    @BeforeAll
    static void setUp() {
        validatorFactory = Validation.buildDefaultValidatorFactory();
        validator = validatorFactory.getValidator();
    }

    @AfterAll
    static void tearDown() {
        validatorFactory.close();
    }

    private Set<String> messages(RegisterRequest req) {
        return validator.validate(req).stream()
                .map(ConstraintViolation::getMessage)
                .collect(Collectors.toSet());
    }

    private RegisterRequest validRequest() {
        RegisterRequest req = new RegisterRequest();
        req.setUsername("nurse01");
        req.setPassword("Nurse@123");
        return req;
    }

    @Test
    void validRequest_shouldPassValidation() {
        assertThat(messages(validRequest())).isEmpty();
    }

    @Test
    void blankUsername_shouldFail() {
        RegisterRequest req = validRequest();
        req.setUsername("   ");
        assertThat(messages(req)).contains("用户名不能为空");
    }

    @Test
    void tooShortUsername_shouldFail() {
        RegisterRequest req = validRequest();
        req.setUsername("ab");
        assertThat(messages(req)).contains("用户名仅支持 3-32 位字母、数字或下划线");
    }

    @Test
    void usernameWithIllegalCharacters_shouldFail() {
        RegisterRequest req = validRequest();
        req.setUsername("护士-01");
        assertThat(messages(req)).contains("用户名仅支持 3-32 位字母、数字或下划线");
    }

    @Test
    void tooLongUsername_shouldFail() {
        RegisterRequest req = validRequest();
        req.setUsername("a".repeat(33));
        assertThat(messages(req)).contains("用户名仅支持 3-32 位字母、数字或下划线");
    }

    @Test
    void tooLongPassword_shouldFail() {
        RegisterRequest req = validRequest();
        req.setPassword("a".repeat(65));
        assertThat(messages(req)).contains("密码长度不能超过 64 位");
    }

    @Test
    void shortPassword_shouldBeDeferredToPasswordPolicy() {
        RegisterRequest req = validRequest();
        req.setPassword("12345");
        // DTO 不校验最小长度，复杂度由服务层 PasswordPolicy 统一拦截
        assertThat(messages(req)).isEmpty();
    }

    @Test
    void invalidEmail_shouldFail() {
        RegisterRequest req = validRequest();
        req.setEmail("not-an-email");
        assertThat(messages(req)).contains("邮箱格式不正确");
    }

    @Test
    void optionalEmailMayBeAbsent() {
        RegisterRequest req = validRequest();
        req.setEmail(null);
        assertThat(messages(req)).isEmpty();
    }

    @Test
    void tooLongDisplayName_shouldFail() {
        RegisterRequest req = validRequest();
        req.setDisplayName("名".repeat(65));
        assertThat(messages(req)).contains("昵称长度不能超过 64 位");
    }

    @Test
    void optionalDisplayNameMayBeAbsent() {
        RegisterRequest req = validRequest();
        req.setDisplayName(null);
        assertThat(messages(req)).isEmpty();
    }
}
